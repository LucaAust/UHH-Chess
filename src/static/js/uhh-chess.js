var config = {
  pieceTheme: '/static/lib/chessboardjs-1.0.0/img/chesspieces/wikipedia/{piece}.png',
  position: current_fen || 'start',
  draggable: true,
  onDragStart: onDragStart,
  onDrop: onDrop,
  promotion: 'q',
}
var board = Chessboard('chess-board', config);
document.getElementById('fen_input').addEventListener('change', function (evt) {
  console.log(this.value);
  board = Chessboard('chess-board', {
    position: this.value,
    pieceTheme: '/static/lib/chessboardjs-1.0.0/img/chesspieces/wikipedia/{piece}.png',
  });
});

document.addEventListener("DOMContentLoaded", function() {


    

    var sec = 0;
    function pad ( val ) { return val > 9 ? val : "0" + val; }
    setInterval( function(){
        document.getElementById("seconds").innerHTML=pad(++sec%60);
        document.getElementById("minutes").innerHTML=pad(parseInt(sec/60,10));
    }, 1000);

    console.log(board.fen());
    board.promotion

    var start_timestamp = Date.now();
    console.log(start_timestamp);
});



function onDragStart(source, piece, position, orientation) {
  // disable black side moving
  return !((orientation === 'white' && piece.search(/^w/) === -1) ||
              (orientation === 'black' && piece.search(/^b/) === -1));
}


function onDrop (source, target, piece, newPos, oldPos, orientation) {
  if (source === target){
    console.log("Not moved!");
    return;
  }

  let old_fen = board.fen()
  console.log("old_fen: "+ old_fen);
  data = {
    'source': source,
    'target': target,
    'piece': piece,
    'new_fen': Chessboard.objToFen(newPos),
    'old_fen': Chessboard.objToFen(oldPos),
    'promotion': is_promotion(board, piece) ? 'q': null,
  }

  api_result = api.put('\\move\\'+api.getCookie('token'), data);
  console.log(api_result);

  if (api_result.error){
    console.log(api_result.info + " Reset to old FEN!");
    console.log(target + '-' +  source);
    board.move(target + '-' + source, promotion='q');
    board.move()

    return 'snapback';
  }
  
  console.log("move: " + api_result.move);
  board.move(api_result.move);
  
}

function is_promotion(curr_board, curr_piece){
  // check promotion for white
  return curr_board.turn() == 'w' &&
  curr_board.from.charAt(1) == 7 &&
  curr_board.to.charAt(1) == 8 &&
  curr_piece.type == 'p' &&
  curr_piece.color == 'w'
}