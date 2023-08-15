import logging
from typing import Union
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src import app, templates, stockfish_instances
from src.views.auth import token_required

log = logging.getLogger()


@app.get('/start/{user_id}/{user_elo}', response_class=HTMLResponse)
async def index(request: Request, user_id: str, user_elo: int, redirect_url: str | None, game_number: int | None):
    log.debug(f"redirect_url: {redirect_url}")
    log.debug(f"game_number: {game_number}")

    return templates.TemplateResponse(
        "start.html", 
        {'request': request, 'start_game_path': f'/new/{user_id}/{user_elo}?redirect_url={redirect_url}&game_number={game_number}'}
    )

@app.get('/new/{user_id}/{user_elo}', response_class=HTMLResponse)
async def new_game(request: Request, user_id: str, user_elo: int, redirect_url: str | None, game_number: int | None, old_game_id: Union[int, None] = None):
    game = await stockfish_instances.new(user_elo, user_id, redirect_url, game_number, old_game_id)
    log.debug(f"Created new game: {game}")

    token = game.token
    
    await game.close()
    return RedirectResponse(url=f"/game/{token}")


@app.get('/game/{token}', response_class=HTMLResponse)
@token_required
async def game(request: Request, token: str):
    game = await stockfish_instances.get(token)

    db_fen = game.board.fen()
    log.debug(f"game.board.gen(): {db_fen}")

    await game.close()

    res = templates.TemplateResponse("game.html", {'request': request, 'fen': db_fen})
    res.set_cookie('token', token, secure=False)

    return res


@app.put('/move/{token}', response_class=JSONResponse)
@token_required
async def move(request: Request, token: str):
    game = await stockfish_instances.get(token)
    # log.debug(game.get_board_visual())
    move = await game.move(request)
    await game.close()
    return move

