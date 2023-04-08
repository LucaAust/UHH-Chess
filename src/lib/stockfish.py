import logging
import json
import traceback
from typing import Any, Tuple, Union, List
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Request
import chess
import chess.engine
from chess import BLACK, SQUARE_NAMES, COLOR_NAMES, piece_symbol, PIECE_SYMBOLS
from fastapi.responses import JSONResponse

from src import log
from src.lib.constants import TIMESTAMP_FORMAT, GAME_DATA_SAVE_DIR
from src.lib.helper import json_serial
from src.lib.sql import SQL

log = logging.getLogger()


class Stockfish():
    async def __init__(self, path: str, token: str, sql_conn: SQL, game_id: int, 
        depth: int = 20, nodes: int = None, redirect_to: Union[str, None] = None,
        max_user_draw_time: float = 30.0,  engine_options = None) -> None:

        self.stop = False
        self.start = datetime.now()
        self.last_interaction = datetime.now()
        self.engine = chess.engine.SimpleEngine.popen_uci(str(path))

        self.board = chess.Board()
        self.game_id = game_id
        self.end_reason = "Unkown (Default value)"
        self.token = token
        self.sql_conn = sql_conn

        self.redirect_to = redirect_to
        self.max_user_draw_time = max_user_draw_time
        self.thinking_time = chess.engine.Limit(
            time=0.1,
            depth=depth,
            nodes=nodes,
            )

        #  make shure the white player starts
        if self.board.turn == BLACK:
            self.chess.Move.null()

        # set UCI settings
        if engine_options:
            self.engine.configure(engine_options)

        await self._load_existing_game_data()
        log.info(f"Start engine with: {self.__dict__}")

    async def close(self):
        if self.engine:
            self.engine.close()

    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def _load_existing_game_data(self):
        await self.load_fen()
        await self._load_existing_start_time()

    async def _load_existing_start_time(self):
        res = await self.sql_conn.query("""
            SELECT
                start
            FROM
                games
            WHERE
                games.id = %(game_id)s
            """,
            {'game_id': self.game_id},
            first=True,
        )

        if res.get('start'):
            self.start = res['start']

    async def _save_move(self, game_id: str, source: str, target: str, piece: str, old_fen: str, new_fen: str, timestamp: Union[datetime, None] = None, promotion_symbol: PIECE_SYMBOLS = None) -> None:

        res =  await self.sql_conn.query("""
            INSERT INTO chess.moves
                (game_id, source, target, old_fen, new_fen, piece, promotion_symbol, t_stamp)
            VALUES
                (
                    %(game_id)s, %(source)s, %(target)s, %(old_fen)s, %(new_fen)s, %(piece)s, %(promotion_symbol)s, NOW(3)
                )
            RETURNING 
                t_stamp + INTERVAL 1 DAY AS t_stamp; 

            """,
            {
                'game_id': int(game_id),
                'source': source,
                'target': target,
                'old_fen': old_fen,
                'new_fen': new_fen,
                'piece': piece,
                'promotion_symbol': promotion_symbol,
                't_stamp': timestamp.strftime(TIMESTAMP_FORMAT)[:3] if timestamp else None,
            },
            first=True,
        )

    async def _get_all_moves(self) -> Tuple[chess.Move]:
        res = await self.sql_conn.query("""
            SELECT
                moves.source, moves.target, moves.promotion_symbol
            FROM
                chess.moves
            RIGHT JOIN
                chess.games
            ON 
                games.id = moves.game_id
            WHERE
                games.token = %(token)s
            ORDER BY
                moves.t_stamp ASC;
        """, 
        {'token': self.token}
        )
        log.debug(f"res: {res}")

        moves: List[chess.Move] = []
        for entry in res:
            moves.append(
                chess.Move(
                    chess.parse_square(entry['source']),
                    chess.parse_square(entry['target']),
                    promotion=PIECE_SYMBOLS.index(entry['promotion_symbol'])
                )
            )
            
        return moves

    async def should_deleted(self) -> bool:
        """Check if this instance sould be deleted.

        Returns:
            bool: Schould be deleted.
        """
        return self.stop or (datetime.now() - self.last_interaction).total_seconds() >  60 * 5

    async def load_fen(self, set_fen: bool = True) -> str:
        """Load the latest FEN from database.

        Arguments:
            set_fen(bool): Should the loaded FEN set to Stockfish. Defaults to True.

        Returns:
            str: Loaded FEN if found else an emptry string.
        """
        res = await self.sql_conn.query("""
            SELECT
                new_fen
            FROM
                chess.moves
            RIGHT JOIN
                chess.games
            ON 
                games.id = moves.game_id
            WHERE
                games.token = %(token)s
            ORDER BY
                moves.t_stamp DESC
            LIMIT 1;
        """, 
        {'token': self.token},
        first=True
        )

        log.debug(f"res: {res}")

        #  make shure the white player starts
        if self.board.turn == BLACK:
            self.chess.Move.null()

        if fen := res.get('new_fen'):
            if set_fen:
                # do each move to detect some end rules
                for curr_move in await self._get_all_moves():
                    self.board.push(curr_move)
            return fen

        return ""

    async def _get_move_duration(self) -> float:
        """Load last KI move and calculate user draw time.
        
        Returns:
            float: Move duration.
        """
        res = await self.sql_conn.query("""
                SELECT
                    t_stamp
                FROM
                    moves
                WHERE
                    game_id = %(game_id)s AND
                    piece != NULL
                ORDER BY
                    t_stamp DESC
                LIMIT 1
            """,
            {'game_id': self.game_id},
            first=True
        )

        if res.get('t_stamp'):
            return (datetime.now() - datetime.strptime(res['t_stamp'], TIMESTAMP_FORMAT)).total_seconds()

        return 0

    async def _check_game_end(self):
        self.end_reason = "Max game time (20min) reached!"
        return {
            "outcome": self.board.is_game_over(),
            "move_timeout": await self._get_move_duration() > self.max_user_draw_time + 10,
            "total_timeout": datetime.now() - self.start > timedelta(minutes=20)
        }

    async def check_game_end(self) -> bool:
        end_results = await self._check_game_end()
        log.debug(f"end_results: {end_results}")
        if any(end_results.values()):
            print(self.board.is_game_over())
            print("Game Ends! Saving reason..")
            await self._save_end_reason()
            return True

        return False

    async def _save_end_reason(self):
        log.debug(f"self.board.outcome(): {self.board.outcome()}")

        outcome = self.board.outcome()
        log.debug(f"outcome: {outcome}")

        args = {
            'end_reasons': outcome.termination.name if outcome else self.end_reason,
            'winner': COLOR_NAMES[outcome.winner] if outcome and outcome.winner else "",
            'token': self.token
        }

        log.debug(f"args: {args}")

        # insert game end reason and remove token to disable loading
        res = await self.sql_conn.query("""
                UPDATE games SET
                    end_reasons = %(end_reasons)s,
                    winning_color = %(winner)s,
                    token = NULL,
                    stop = NOW()
                WHERE
                    token = %(token)s
            """,
            query_args=args
        )
        log.debug(f"res: {res}")

        await self.write_game_data()

    async def write_game_data(self) -> None:
        """Save game data as JSON in `constants.GAME_DATA_SAVE_DIR`."""
        game_data = await self.sql_conn.query("""
            SELECT
                start, stop,
                user_elo, ki_elo,
                user_id, end_reasons,
                winning_color,
                source, target,
                new_fen, old_fen,
                piece,t_stamp
            FROM
                games
            INNER JOIN
                moves
            ON
                moves.game_id = games.id
            WHERE
                games.id = %(game_id)s
            ORDER BY
                moves.t_stamp ASC
            """,
            {'game_id': self.game_id}
        )

        if not GAME_DATA_SAVE_DIR.exists():
            GAME_DATA_SAVE_DIR.mkdir(parents=True)

        file_path = GAME_DATA_SAVE_DIR  / f"{game_data[-1]['user_id']}_{self.game_id}_{self.token}.json"
        log.info(f"Save game data to: {file_path.absolute()}")

        try:
            with open(file_path, 'w+') as file:
                json.dump(game_data, file, indent=4, ensure_ascii=False, default=json_serial)
        except Exception:
            log.exception(traceback.format_exc())
            log.error(f"Save game data Failed! Token: {self.token}")

    async def _ki_move(self) -> Tuple[chess.Move, bool]:
        """Run KI move.

        Returns:
            Tuple[chess.Move, bool]: KI move and whether the game was finished. 
        """
        ki_move = self.engine.play(self.board, self.thinking_time, game=self.game_id).move
        self.board.push(ki_move)

        return (ki_move, await self.check_game_end())

    async def move(self, request: Request, game_id: int) -> dict:
        """Validate the move and save the results in the database.

        Args:
            request (Request): Current API request. 
            game_id (int): Game ID.

        Returns:
            dict: KI move, game end.
        """
        log.debug(self.board)
        self.last_interaction = datetime.now()
        data = (await request.json()).get('data')
        log.debug(f"data: {data}")

        if not data:
            return JSONResponse({'error': True, 'info': "Missing data!"}, status_code=500)

        try:
            user_move = chess.Move.from_uci(f"{data['source']}{data['target']}{'q' if data['promotion'] else ''}")
        except ValueError:
            return {'error': True, 'info': "Null move!"}
        except Exception:
            print(traceback.format_exc())

        log.debug(f"promotion: {user_move.promotion}")
        log.debug(f"move: {user_move}")
        log.debug("Black" if self.board.turn == BLACK else "WHITE")

        # check if move legal 
        if user_move not in self.board.legal_moves:
            log.debug(f"Illegal move: {user_move}")
            return {'error': True, 'info': "Illegal move!"}

        # user move
        user_old_fen = self.board.fen()
        self.board.push(user_move)
        user_new_fen = self.board.fen()

        result = {
            'game_end': await self.check_game_end(),
        }

        ki_old_fen = self.board.fen()
        game_end_ki = False
        if not result['game_end']:
            # KI move
            ki_move, game_end_ki = await self._ki_move()
            result['move'] = (SQUARE_NAMES[ki_move.from_square], SQUARE_NAMES[ki_move.to_square])

        # save the move after evaluation to have a later timestamp
        # and the user has nearly the draw time of 30 seconds
        # save user move
        await self._save_move(
            game_id=game_id,
            source=data['source'],
            target=data['target'],
            piece=data['piece'],
            old_fen=user_old_fen,
            new_fen=user_new_fen,
            timestamp=datetime.now(),
            promotion_symbol=piece_symbol(user_move.promotion) if user_move.promotion else None  # user promotion currently only 'q'
        )

        if not result['game_end']:
            # save KI move
            await self._save_move(
                game_id=game_id,
                source=SQUARE_NAMES[ki_move.from_square],
                target=SQUARE_NAMES[ki_move.to_square],
                piece=None,
                old_fen=ki_old_fen,
                new_fen=self.board.fen(),
                timestamp=datetime.now(),
                promotion_symbol=piece_symbol(ki_move.promotion) if ki_move.promotion else None # ki promotion can be every possible piece
            )
            result['game_end'] = game_end_ki or result['game_end']

        if result['game_end']:
            result['redirect_to'] = self.redirect_to
            self.stop = True
            log.info("Close current Stockfish instance")
            self.engine.close() 

        log.debug(result)
        return result
