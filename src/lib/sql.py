import logging
from typing import Any, Union
import mariadb


log = logging.getLogger()


class SQL:
    def __init__(self, database: str, user: str, password : str, port: Union[int, None] = 3306 , host: Union[str, None] = "127.0.0.1") -> None:
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.conn = None

    def connect(self):

        if self.conn:
            return

        # Connect to MariaDB Platform
        try:
            self.conn = mariadb.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database,
                reconnect=True,
            )
        except mariadb.Error as e:
            log.exception(f"Error connecting to MariaDB Platform: {e}")
            self.conn = None
            return


    async def query(self, query : str, query_args : Any = None, first: bool = False):
        self.connect()

        # print(query, query_args)
        with self.conn.cursor(dictionary=True) as conn:
            conn.execute(query, query_args)
            self.conn.commit()
            try:
                result = (conn.fetchone() if first else conn.fetchall()) or {}
            except mariadb.ProgrammingError:
                return {'rowcount': conn.rowcount}

        log.debug(f"DB result: {result}")
        return result
