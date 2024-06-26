import * as chessjs from "/static/lib/chess.js-0.13.4/chess.js"

var board;
var board_elem;
var countdown_elem;
var countdown_id;
var countdown_time = 30;
var curr_countdown_time = 30;
var curr_redirect_countdown_time = 10;
var game_ended = false;
var game = new chessjs.Chess(current_fen || chessjs.DEFAULT_POSITION);


document.addEventListener("DOMContentLoaded", function() {

    console.log('current_fen: ' + current_fen);
    countdown_elem = document.getElementById('countdown');
    board_elem = document.getElementById('chess-board');
    var cfg = {
        snapbackSpeed: 100,
        appearSpeed: 1500,
        draggable: true,
        onDragStart: onDragStart,
        onDrop: onDrop,
        onSnapEnd: onSnapEnd,
        pieceTheme: '/static/lib/chessboardjs-1.0.0/img/chesspieces/wikipedia/{piece}.png',
        position: current_fen || 'start',
        draggable: true,
    };

    board = new ChessBoard('chess-board', cfg);
    $(window).resize(board.resize);
    create_countdown()
    updateStatus(game);
})

function updateStatus(game){
    var status = '';
    
    var moveColor = 'White';
    if (game.turn() === 'b') {
        moveColor = 'Black';
    }
    
    // checkmate?
    if (game.in_checkmate() === true) {
        status = 'Game over, ' + moveColor + ' is in checkmate.'
    }
    
    // draw?
    else if (game.in_draw() === true) {
        status = 'Game over, drawn position';
    }
    
    // game still on
    else {
        status = moveColor + ' to move';
    
        // check?
        if (game.in_check() === true) {
        status += ', ' + moveColor + ' is in check';
        }
    }
}

function onDragStart(source, piece, position, orientation) {
    // disable black side moving and after game end
    return !(
        (orientation === 'white' && piece.search(/^w/) === -1) ||
        (orientation === 'black' && piece.search(/^b/) === -1) ||
        game_ended
    );
}


function onDrop (source, target, piece, newPos, oldPos, orientation) {
    if ((source == target) || game_ended ) return 'snapback'

    // see if the move is legal
    console.log(game.ascii());
    let _is_promotion = is_promotion({
        chess: game,
        move: {from: source, to: target}
    });
    console.log("_is_promotion: "+_is_promotion);

    let game_old_fen = game.fen()
    console.log(game);
    let move = game.move({
        from: source,
        to: target,
        promotion: 'q'
    });
    
    console.log(game.ascii());

    // illegal move
    if (move === null) return 'snapback';
    
    let data = {
        'source': source,
        'target': target,
        'piece': piece,
        'new_fen': game.fen(),
        'old_fen': game_old_fen,
        'promotion': _is_promotion ? 'q' : null,
    }

    let api_result = api.put('\\move\\'+api.getCookie('token'), data);
    console.log(api_result);

    if (api_result.error){
        console.log(api_result.info + " Reset to old FEN!");
        console.log(target + '-' +  source);
        board.move(target + '-' + source, false);

        return 'snapback';
    }
    

    console.log("move: " + api_result.move);
    if (api_result.move){
        let ki_move = game.move({
            from: api_result.move[0],
            to: api_result.move[1],
            promotion: 'q'
        });

        console.log("ki_move:" + ki_move);
    }

    console.log("game.fen(): " + game.fen());
    updateStatus(game);

    if (api_result.game_end){
        game_ended = true
        countdown_elem.style.display = 'none'; // hide countdown


        if (api_result.redirect_url){
            board_elem.classList.add('greyscale');

            if (api_result.new_game_number){
                let redirect = '/new/'+api_result.user_id + '/' + api_result.user_elo + 
                '?redirect_url=' + api_result.redirect_url + '&old_game_id=' + api_result.game_id + 
                '&game_number=' + api_result.new_game_number;
                console.log("redirect: " + redirect);
                window.location = redirect;
            }

            // show redirect text
            let game_end_hint_elem = document.getElementById('game_end_hint');
            game_end_hint_elem.innerHTML = 'The game is finished.<br>You will be redirected in <span id="redirect_countdown">'+curr_redirect_countdown_time+'</span> seconds.<br>In the case of an error, please click on the following link:<br><br><a href="'+api_result.redirect_url+'">'+api_result.redirect_url+'</a>'
            
            document.getElementById('game-end-hint-container').style.display = 'block';

            setInterval(function() {redirect_countdown(api_result.redirect_url)}, 1000);
            console.log("api_result.redirect_url: " + api_result.redirect_url);
        }else{
            document.getElementById('redirect_error').display = 'block';
        }
    }

    create_countdown();
}

// works only for WHITE
function is_promotion(cfg) {
    var piece = cfg.chess.get(cfg.move.from);
    if (
        cfg.chess.turn() == 'w' && // check white
        cfg.move.from.charAt(1) == 7 && // check if is move from column 7
        cfg.move.to.charAt(1) == 8 && // check if is move to column 8
        piece.type == 'p' && // check piece type
        piece.color == 'w' // check piece color
    ){

        // check for valid promotion move
        if (chessjs.Chess(game.fen()).move({from: cfg.move.from, to: cfg.move.to, promotion: 'q'})) {
                return true;
        } else {
                return false;
        }
    }
}

function redirect_countdown(redirect_url){
    document.getElementById('redirect_countdown').innerText = curr_redirect_countdown_time
    curr_redirect_countdown_time--;

    if (curr_redirect_countdown_time <= 0){
        window.location = redirect_url;
    }
}

function onSnapEnd(){
    board.position(game.fen());
}

function create_countdown(){
    if (countdown_id){
        clearInterval(countdown_id);
        countdown_id = null;
        curr_countdown_time = countdown_time;
    }

    countdown_id = setInterval(countdown, 1000);
}


function countdown() {
    if (curr_countdown_time <= 10){
        countdown_elem.classList.add('red');
    }else{
        countdown_elem.classList.remove('red');
    }

    if (curr_countdown_time == -1) {
        clearInterval(countdown_id);
    } else {
        countdown_elem.innerHTML = curr_countdown_time;
        curr_countdown_time--;
    }
}