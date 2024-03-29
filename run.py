import logging
import uvicorn
import asyncio

from src import app
from src.lib.constants import Color

log = logging.getLogger()

def main(**kwargs):
    log.debug(kwargs)
    log.info(f"Start new game at: {Color.BOLD}{Color.GREEN}http://0.0.0.0:8000/start/example/1285?redirect_url=https://www.startpage.com/{Color.END*2}")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    log.debug("start from __name__ == __main__")
    main()

