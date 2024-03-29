from configparser import NoOptionError, NoSectionError
import logging
import json
import traceback
from typing import Tuple, Union, List, Dict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Request
import chess
import chess.engine
from chess import BLACK, SQUARE_NAMES, COLOR_NAMES, PIECE_SYMBOLS, Piece, piece_symbol, square_file
from fastapi.responses import JSONResponse

from src import log, config
from src.lib.constants import TIMESTAMP_FORMAT, GAME_DATA_SAVE_DIR
from src.lib.helper import json_serial
from src.lib.sql import SQL

log = logging.getLogger()


class Stockfish():
    async def __init__(self, path: str, token: str, sql_conn: SQL, game_id: int, 
        depth: int = 20, nodes: int = None, redirect_url: str | None = None,
        max_user_draw_time: float = 30.0,  engine_options = None, game_number: int | None = None,
        first_game_start: datetime | None = datetime.now() ) -> None:

        self.start = datetime.now()
        self.engine = chess.engine.SimpleEngine.popen_uci(str(path))

        self.board = chess.Board()
        self.game_id = game_id
        self.end_reason = "Unkown (Default value)"
        self.first_game_start = first_game_start
        self.max_game_time = 20  # in minutes
        self.token = token
        self.sql_conn = sql_conn

        self.redirect_url = redirect_url
        self.game_number = game_number
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
        """Stop and close engine."""
        if self.engine:
            self.engine.close()

    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def _load_existing_game_data(self):
        """Load existing game data into current instance."""
        await self.load_fen()
        await self._load_existing_start_time()

    async def _load_existing_start_time(self):
        """Load game start time."""
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

    async def _save_move(
            self,source: str, target: str, piece: Union[Piece, None], 
            old_fen: str, new_fen: str, timestamp: Union[datetime, None] = None, promotion_symbol: PIECE_SYMBOLS = None
            ) -> None:
        """Insert move into database.

        Arguments:
            source(str): Move source field
            target(str): Move target field
            piece(Union[Piece, None]): Moved piece. If None it will be calculated by old_fen and new_fen.
            old_fen(str): FEN before move
            new_fen(str): FEN after move
            timestamp(Union[datetime, None]): date and time of move. Defaults to None.
            promotion_symbol(chess.PIECE_SYMBOLS): Symbol of promotion, Defaults to None.

        """
        if piece is None:
            piece = chess.Board(old_fen).piece_at(chess.parse_square(source))

        await self.sql_conn.query("""
            INSERT INTO chess.moves
                (game_id, source, target, old_fen, new_fen, piece, promotion_symbol, t_stamp, castling, color)
            VALUES
                (
                    (SELECT id FROM games WHERE token = %(token)s), %(source)s, %(target)s, %(old_fen)s, %(new_fen)s, %(piece)s, %(promotion_symbol)s, NOW(3), %(castling)s, %(color)s
                )

            """,
            {
                'token': self.token,
                'source': source,
                'target': target,
                'old_fen': old_fen,
                'new_fen': new_fen,
                'castling': await self.get_castling(
                    old_fen=old_fen,
                    move = chess.Move(
                        chess.parse_square(source),
                        chess.parse_square(target),
                    )
                ),
                'piece': piece.symbol(),
                'color': COLOR_NAMES[piece.color],
                'promotion_symbol': promotion_symbol,
                't_stamp': timestamp.strftime(TIMESTAMP_FORMAT)[:3] if timestamp else None,
            },
        )

    async def _get_all_moves(self) -> Tuple[chess.Move]:
        """Load all moves from database

        Returns:
            Tuple[chess.Move]: List of moves

        """
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

    async def get_end_results(self) -> Dict[str, bool]:
        """Check the game end conditions

        Returns:
            Dict[str, bool]: Checked conditions with result
        """
        return {
            "outcome": self.board.is_game_over(),
            #"move_timeout": await self._get_move_duration() > self.max_user_draw_time + 10,
            "total_timeout": datetime.now() - self.first_game_start > timedelta(minutes=self.max_game_time)
        }

    async def check_game_end(self) -> bool:
        """Check if the game is finished. If yes then the data will be written to the output file

        Returns:
            bool: Game finished
        """
        end_results = await self.get_end_results()
        log.debug(f"end_results: {end_results}")

        if any(end_results.values()):
            print("Game Ends! Saving reason..")
            if end_results['total_timeout']:
                self.end_reason = f"Total timeout of {self.max_game_time}min reached"

            await self._save_end_reason()
            await self.write_game_data()
            return True

        return False

    async def _save_end_reason(self):
        """Save the end reason with player color (only if there is a winner)"""
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
                    stop = NOW()
                WHERE
                    token = %(token)s
            """,
            query_args=args
        )
        log.debug(f"res: {res}")

    async def _load_game_output_data(self) -> List:
        """Load all required game data wich must be stored in the output file."""
        return await self.sql_conn.query("""
            SELECT
                start, stop,
                user_elo, ki_elo,
                game_number,
                user_id, end_reasons,
                winning_color,
                source, target,
                new_fen, old_fen,
                piece,t_stamp,
                castling, color
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

    async def calc_game_data(self) -> List:
        """Load and calculate data wich must be stored in the output file.

        Calculated entries: draw_time, overdrawn, move_number, user_move_count, avg_move_duration

        Returns:
            List: _description_
        """
        game_data = await self._load_game_output_data()
        user_draw_times = []

        for i in range(0 ,len(game_data)):
            # check if move tooks more than in self.max_user_draw_time allowed
            game_data[i]['overdrawn'] = False
            prev_draw_ts = game_data[i-1]['t_stamp'] if not i == 0 else game_data[0]['start']
            cur_draw_ts = game_data[i]['t_stamp']
            if prev_draw_ts + timedelta(seconds=self.max_user_draw_time) < cur_draw_ts:
                game_data[i]['overdrawn'] = True

            # get move duration
            draw_time: timedelta = cur_draw_ts - prev_draw_ts

            game_data[i]['draw_time'] = round(draw_time.total_seconds(), 3)
            user_draw_times.append(
                draw_time
            )

            game_data[i]['move_number'] = i + 1

        user_move_count = len(user_draw_times)
        game_data[-1]['user_move_count'] = user_move_count
        game_data[-1]['avg_move_duration'] = round(
            (sum(user_draw_times, timedelta()) / user_move_count).total_seconds(), 3
        )

        return game_data

    async def get_output_path(self, user_id: int, game_number: int) -> Path:
        """Get the filepath where to store the game output data.

        Args:
            user_id (int): Current user ID
            game_number (int): Number of the Game of current user

        Returns:
            Path: Target filepath
        """
        try:
            output_dir = Path(config.get('game', 'data_save_dir'))
        except (NoOptionError, NoSectionError):
            output_dir = GAME_DATA_SAVE_DIR

        output_dir = output_dir / f"{user_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir  / f"{user_id}_{game_number}_{self.token}.json"
        log.info(f"Save game data to: {file_path.absolute()}")

        return file_path

    async def write_game_data(self) -> None:
        """Save game data as JSON in `constants.GAME_DATA_SAVE_DIR`."""
        game_data = await self.calc_game_data()
        file_path = await self.get_output_path(
            game_data[-1]['user_id'],
            game_data[-1]['game_number']
        )

        try:
            with open(file_path, 'w+') as file:
                json.dump(game_data, file, indent=4, ensure_ascii=False, default=json_serial)
        except Exception:
            log.exception(traceback.format_exc())
            log.error(f"Save game data Failed! Token: {self.token}")

    async def _ki_move(self) -> chess.Move:
        """Run engine move and write to database.

        Returns:
            Tuple[chess.Move, bool]: KI move and whether the game was finished. 
        """

        old_fen = self.board.fen()
        ki_move = self.engine.play(self.board, self.thinking_time, game=self.game_id).move
        self.board.push(ki_move)

        await self._save_move(
            source=SQUARE_NAMES[ki_move.from_square],
            target=SQUARE_NAMES[ki_move.to_square],
            piece=None,
            old_fen=old_fen,
            new_fen=self.board.fen(),
            timestamp=datetime.now(),
            promotion_symbol=piece_symbol(ki_move.promotion) if ki_move.promotion else None # ki promotion can be every possible piece
        )

        return ki_move

    async def _delete_token(self):
        """Set game token in db to NULL"""
        await self.sql_conn.query("UPDATE games SET token = %(token)s", {'token': self.token})

    @staticmethod
    async def get_castling(old_fen: str, move: chess.Move) -> str:
        """Get castling notation.

        https://de.wikipedia.org/wiki/Forsyth-Edwards-Notation#Rochaderechte-Kodierung

        Args:
            old_fen (str): FEN before move.
            fen2 (chess.Move): Current move.

        Returns:
            str: Castle notation
        """
        

        if chess.Board(old_fen).is_castling(move):
            if square_file(move.to_square) > square_file(move.from_square):  # kingside castling move
                return '0-0'
            elif square_file(move.to_square) < square_file(move.from_square):  # queenside castling move
                return '0-0-0'

        return ''

    async def get_redirect_data(self) -> Dict:
        """Load redirect data from database.
        
        Returns:
            dict: reqired data vor redirect.
        """
        log.debug("Load redirect data from database")
        return await self.sql_conn.query(
            """
            SELECT 
                id as game_id,
                game_number + 1 as new_game_number,
                first_game_start,
                redirect_url,
                user_id,
                user_elo,
                (SELECT TRUE) as game_end
            FROM 
                games
            WHERE
                token = %(token)s;
            """, {'token': self.token},
            first=True
        )

    async def _user_move(self, move_data: Dict[str, str]) -> None:
        """Validate and save user move.

        Args:
            move_data (Dict[str, str]): Move data

        :raises: :exc:`InvalidMoveError` if move_data are invalid.
        """
        user_move = chess.Move.from_uci(f"{move_data['source']}{move_data['target']}{'q' if move_data['promotion'] else ''}")

        log.debug(f"promotion: {user_move.promotion}")
        log.debug(f"move: {user_move}")

        # check if user move legal 
        if user_move not in self.board.legal_moves:
            log.debug(f"Illegal move: {user_move}")
            return {'error': True, 'info': "Illegal move!"}

        # user move
        user_old_fen = self.board.fen()
        self.board.push(user_move)

        # save user move
        await self._save_move(
            source=move_data['source'],
            target=move_data['target'],
            piece=Piece.from_symbol(move_data['piece'][-1]),
            old_fen=user_old_fen,
            new_fen=self.board.fen(),
            timestamp=datetime.now(),
            promotion_symbol=piece_symbol(user_move.promotion) if user_move.promotion else None  # user promotion currently only 'Q'
        )

    async def move(self, request: Request) -> dict:
        """Validate the move and save the results in the database.

        Args:
            request (Request): Current API request.
            game_id (int): Game ID.

        Returns:
            dict: Engine move and game end.
        """
        data = (await request.json()).get('data')
        log.debug(f"data: {data}")

        if not data:
            log.info("No data in request found!")
            return JSONResponse({'error': True, 'info': "Missing data!"}, status_code=500)

        # do user move
        try:
            await self._user_move(data)
        except ValueError:
            return {'error': True, 'info': "Null move!"}
        except Exception:
            print(traceback.format_exc())
            return {'error': True, 'info': "Invalid move or data."}

        result = {
            'game_end': await self.check_game_end(),
        }

        if not result['game_end']:
            # engine move
            ki_move= await self._ki_move()
            result['move'] = (SQUARE_NAMES[ki_move.from_square], SQUARE_NAMES[ki_move.to_square])

        try:
            result['game_end'] = await self.check_game_end() or result['game_end']

            if result['game_end']:
                if datetime.now() - self.first_game_start > timedelta(minutes=self.max_game_time):
                    result['redirect_url'] = self.redirect_url
                    log.info("Close current Stockfish instance")
                else:
                    result = await self.get_redirect_data()

                await self._delete_token()

        except Exception:
            log.exception(traceback.format_exc())

        log.debug(result)
        self.close()
        return result
