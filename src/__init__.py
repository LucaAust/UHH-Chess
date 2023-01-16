import configparser
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseSettings

from src.lib.astl_logger import AstlLogger
from src.lib.sql import SQL


class Settings(BaseSettings):
    openapi_url: str = None


config = configparser.ConfigParser()
config.read('settings.ini')

print(f"config['log']['log_to_stdout']: {config['log']['log_to_stdout']}")
AstlLogger(Path(), config['log'].getint('level'), config['log'].getboolean('log_to_stdout'))
log = logging.getLogger()

app = FastAPI(
    openapi_url=None,
    redoc_url=None,
)

origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
) 

src_path = Path().cwd().joinpath('src')
app.mount("/static", StaticFiles(directory=Path(src_path, 'static')), name="static")

templates = Jinja2Templates(directory=Path(src_path, 'templates'))

# can only secure if a fqdn is available
SECURE_COOKIE = True

try:
    SECURE_COOKIE = config['cookie']['secure']
except Exception:
    pass

sql_conn = SQL(
     database=config['database']['name'],
     user=config['database']['user'],
     password=config['database']['password'],
     port=config['database'].getint('port'),
     host=config['database'].get('host'),
)
sql_conn.connect()

from src.lib.stockfish_wrapper import StockfishWrapper
stockfish_instances = StockfishWrapper(
    sql_conn,
    minimum_thinking_time=20,
    config=config,
)

from src.views import *
