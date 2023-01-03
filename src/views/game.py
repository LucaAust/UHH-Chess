import logging
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src import app, templates, stockfish_instances
from src.views.auth import token_required

log = logging.getLogger()


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {'request': request})

@app.get('/new/{user_id}/{user_elo}', response_class=HTMLResponse)
async def new_game(request: Request, user_id: str, user_elo: int):
    res = await stockfish_instances.new(user_elo, user_id)
    log.debug(f"Created new game: {res}")
    return RedirectResponse(url=f"/game/{res.token}")


@app.get('/game/{token}', response_class=HTMLResponse)
@token_required
async def game(request: Request, token: str, game_id: int = 0):
    log.debug(f"get game with id: {game_id}")
    game = await stockfish_instances.get(token)

    db_fen = await game.load_fen(set_fen=False)
    log.debug(f"game.get_db_fen(): {db_fen}")

    res = templates.TemplateResponse("index.html", {'request': request, 'fen': db_fen})
    res.set_cookie('token', token, secure=False)

    return res


@app.put('/move/{token}', response_class=JSONResponse)
@token_required
async def move(request: Request, token: str, game_id: int = 0):
    game = await stockfish_instances.get(token)
    # log.debug(game.get_board_visual())
    return await game.move(request, game_id)

