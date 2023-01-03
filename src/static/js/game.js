import * as chessjs from "/static/lib/chess.js-0.13.4/chess.js"

var board;
var board_elem;
var countdown_elem;
var countdown_id;
var countdown_time = 30;
var curr_countdown_time = 30;
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
    // disable black side moving
    return !((orientation === 'white' && piece.search(/^w/) === -1) ||
                (orientation === 'black' && piece.search(/^b/) === -1));
}


function onDrop (source, target, piece, newPos, oldPos, orientation) {
    if (source == target) return 'snapback' 

    // see if the move is legal
    console.log(game.ascii());
    let game_old_fen = game.fen()
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
    }

    // board.position(data.new_fen);
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
        board_elem.style.display = 'none';
        countdown_elem.style.display = 'none';

        if (api_result.redirect_to){
            window.location = api_result.redirect_to;
        }else{
            document.getElementById('redirect_error').display = 'block';
        }
    }

    create_countdown();
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
    }

    if (curr_countdown_time == -1) {
        clearInterval(countdown_id);
        countdown_elem.classList.remove('red');
    } else {
        countdown_elem.innerHTML = curr_countdown_time;
        curr_countdown_time--;
    }
}