import logging
from typing import Union
from pathlib import Path
from configparser import ConfigParser

import psutil

from src.lib.stockfish import Stockfish
from src.lib.sql import SQL

log = logging.getLogger()


class StockfishWrapper():
    def __init__(self, sql_conn: SQL, minimum_thinking_time: int, config: ConfigParser) -> None:
        self.config = config

        self.game_id: int = 0
        self.depth = self.config['stockfish']['depth']
        self.minimum_thinking_time = minimum_thinking_time
        self.instances = {}
        self.stockfish_path = self.config['stockfish']['path']
        self.stockfish_log_path = Path(__file__).parent.parent.joinpath('log', 'stockfish_debug.log')
        
        self.reduce_elo_points = self.config['stockfish'].getint('reduce_elo_points', 400)
        self.cpu_threads = psutil.cpu_count()

        self.sql_conn = sql_conn

        if not self.stockfish_path or not Path(self.stockfish_path).exists():
            raise FileNotFoundError(f"Could not find Stockfish at path '{self.stockfish_path}'")

        log.debug(f"Create StockfishWrapper. {self.__dict__}")

    async def check_ram(self):
        """Check if enough RAM is available to start a new Stockfish instace.

        Raises:
            MemoryError: Rais if free RAM < 512 MB
        """
        if psutil.virtual_memory().available / 1024 / 1024 < 512:
            raise MemoryError("Not enough memmory to create a new Stockfish instance!")

    async def _get_game_info(self, token: str):
        return await self.sql_conn.query(
            "SELECT id AS game_id, user_elo, token, redirect_url, game_number, first_game_start FROM games WHERE token = %(token)s AND stop IS NULL",
            {'token': token}, 
            first=True,
        )

    async def get(self, token: str) -> Union[Stockfish, None]:        
        game_info = await self._get_game_info(token)

        log.debug(f"game_info: {repr(game_info)}")
        if not game_info:
            return None

        return await self._new_instance(**game_info)

    async def _calc_engine_elo(self, user_elo):
        elo = user_elo - self.reduce_elo_points
        if elo < 1349:
            log.info(f"Target ELO '{elo}' is to small! Auto set to 1350")
            elo = 1350
        elif elo > 2850:
            log.info(f"Target ELO '{elo}' is to large! Auto set to 2850")
            elo = 2850

    async def _get_UCI_params(self, user_elo: int):
        return {
                    'UCI_LimitStrength': self.config['stockfish'].getboolean('UCI_LimitStrength'),
                    'UCI_Elo': await self._calc_engine_elo(user_elo),
                    'Slow Mover': self.config['stockfish'].getint('Slow_Mover'),
                    'Threads': self.cpu_threads,
                    'Hash': self.config['stockfish'].getint('hash'),
                }

    async def _new_instance(self, token: str, game_id: int, user_elo: int, first_game_start, redirect_url: str | None, game_number: int | None):
        await self.check_ram()

        return await Stockfish(
            str(self.stockfish_path),
            token=token,
            sql_conn=self.sql_conn,
            game_id=game_id,
            engine_options=await self._get_UCI_params(user_elo),
            depth=self.depth,
            redirect_url=redirect_url,
            game_number=game_number,
            first_game_start=first_game_start,
        )


    async def _clear_instances(self):
        to_delete = [e.token for e in self.instances.values() if e.should_deleted()]
        log.debug(f"Stockfish instances to delete: {to_delete}")
        for key in to_delete:
            del self.instances[key]

    async def new(self, elo: int, user_id: str, redirect_url: str | None, game_number: int | None, old_game_id = None) -> Stockfish:
        res = await self.sql_conn.query("""
                INSERT INTO games
                    (ki_elo, user_elo, user_id, redirect_url, game_number, first_game_start)
                VALUES
                    (%(ki_elo)s ,%(user_elo)s, %(user_id)s, %(redirect_url)s, %(game_number)s, (SELECT g.first_game_start FROM games as g WHERE g.id = %(old_game_id)s) )
                RETURNING token, id AS game_id, user_elo, redirect_url, game_number, first_game_start;
            """,
            {
                'user_id': user_id, 'user_elo': elo, 'ki_elo': await self._calc_engine_elo(elo), 'redirect_url': redirect_url, 
                'game_number': game_number, 'old_game_id': old_game_id,
            },
            first=True
        )

        if not res:
            raise Exception(f"Could not create new game!")
        
        print(res)
        return await self._new_instance(**res)
