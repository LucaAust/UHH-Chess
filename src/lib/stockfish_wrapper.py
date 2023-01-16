import logging
from configparser import ConfigParser
from typing import Union
from pathlib import Path

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
        
        self.add_elo_points = self.config['stockfish'].getint('add_elo_points', 400)
        self.cpu_threads = psutil.cpu_count()

        self.sql_conn = sql_conn

        if not self.stockfish_path or not Path(self.stockfish_path).exists():
            raise FileNotFoundError(f"Could not find Stockfish at path '{self.stockfish_path}'")

        log.debug(f"Create StockfishWrapper. {self.__dict__}")

    async def check_ram(self):
        """Check if enough RAM is available to start a new Stockfish instace.

        Raises:
            MemoryError: _description_
        """
        if psutil.virtual_memory().available / 1024 / 1024 < 512:
            raise MemoryError("Not enough memmory to create a new Stockfish instance!")

    async def _get_game_info(self, token: str):
        return await self.sql_conn.query(
            "SELECT id AS game_id, user_elo, token FROM games WHERE token = %(token)s AND stop = 0;",
            {'token': token}, 
            first=True,
        )

    async def get(self, token: str) -> Union[Stockfish, None]:        
        game_info = await self._get_game_info(token)

        log.debug(f"game_info: {repr(game_info)}")
        if not game_info:
            return None

        # return existing instance
        if instance := self.instances.get(token, False):
            return instance

        # crate new instance
        self.instances[token] = await self._new_instance(**game_info)
        return self.instances[token]

    async def _get_UCI_params(self, user_elo):
        elo = user_elo + self.add_elo_points
        if elo < 1349:
            log.info(f"Target ELO '{elo}' is to small!")
            elo = 1350
        elif elo > 2850:
            log.info(f"Target ELO '{elo}' is to large!")
            elo = 2850

        return {
                    'UCI_LimitStrength': self.config['stockfish'].getboolean('UCI_LimitStrength'),
                    'UCI_Elo': elo,
                    'Slow Mover': self.config['stockfish'].getint('Slow_Mover'),
                    'Threads': self.cpu_threads,
                    'Hash': self.config['stockfish'].getint('hash'),
                }

    async def _new_instance(self, token: str, game_id: int, user_elo: int):
        await self.check_ram()

        return Stockfish(
            str(self.stockfish_path),
            token=token,
            sql_conn=self.sql_conn,
            game_id=game_id,
            engine_options=await self._get_UCI_params(user_elo),
            depth=self.depth,
            redirect_to=self.config['game']['redirect_to'],
        )


    async def _clear_instances(self):
        to_delete = [e.token for e in self.instances.values() if e.should_deleted()]
        log.debug(f"Stockfish instances to delete: {to_delete}")
        for key in to_delete:
            del self.instances[key]
                

    async def new(self, elo: int, user_id: str) -> Stockfish:

        res = await self.sql_conn.query("""
            INSERT INTO games
                (ki_elo, user_elo, user_id)
            VALUES
                (%(ki_elo)s ,%(user_elo)s, %(user_id)s)
            RETURNING token, id AS game_id, user_elo;
        """,
        {'user_id': user_id, 'user_elo': elo, 'ki_elo': elo + self.add_elo_points},
        first=True
        )

        if not res:
            raise Exception(f"Could not create new game!")

        await self._clear_instances()

        print(res)
        self.instances[res['token']] = await self._new_instance(**res)

        return self.instances[res['token']]
