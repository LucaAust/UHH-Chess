import logging
from functools import wraps

from fastapi import HTTPException

from src import sql_conn, log

log = logging.getLogger()


def token_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        log.debug(f"Auth user: {kwargs}")
        token = kwargs.get('token')
        if not token:
            raise HTTPException(403)
        
        res = await sql_conn.query("""
        SELECT id FROM 
            games
        WHERE
            token = %(token)s AND
            stop = 0;
        """,
        {'token': token},
        first=True,
        )

        game_id = res.get('id')
        log.debug(f"game_id: {game_id}")
        if not game_id:
            print(f"raw_path: {kwargs['request']['raw_path']}")
            # print(f"headers: {kwargs['request']['headers']}")
            raise HTTPException(404)

        log.debug(f"valid token: {token}")
        kwargs['game_id'] = game_id
        return await func(*args, **kwargs)

    return wrapper