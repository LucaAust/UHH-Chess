
# create database and user
CREATE DATABASE chess CHARACTER SET utf8mb4 COLLATE utf8mb4_german2_ci;
CREATE USER 'chess_backend'@localhost IDENTIFIED BY 'ue78!9*#o4bZgnqu2G';
GRANT ALL ON `chess`.* TO 'chess_backend'@localhost;

CREATE TABLE chess.games (
	id BIGINT UNSIGNED auto_increment NOT NULL PRIMARY KEY,
	`start` TIMESTAMP DEFAULT NOW() NOT NULL,
	stop TIMESTAMP DEFAULT NULL,
	token VARCHAR(64) DEFAULT sha2(uuid(), 0) NULL,
	user_elo INT UNSIGNED NOT NULL,
	ki_elo INT UNSIGNED NOT NULL,
	user_id varchar(100) NOT NULL,
	end_reasons VARCHAR(100) DEFAULT NULL NULL,
	winning_color VARCHAR(100) NULL
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_german2_ci;


CREATE TABLE chess.moves (
	game_id BIGINT UNSIGNED NOT NULL,
	source CHAR(2) NOT NULL,
	target CHAR(2) NOT NULL,
	new_fen VARCHAR(100) NOT NULL,
	old_fen VARCHAR(100) NOT NULL,
	piece CHAR(2) NULL,
	promotion_symbol CHAR NULL;	 -- ALTER TABLE chess.moves ADD promotion_symbol CHAR NULL;    Use CHAR to allow later an easy change from queen(currently the default and only possible) to other
	t_stamp TIMESTAMP(3) DEFAULT NOW(3) NOT NULL,
	CONSTRAINT NewTable_FK FOREIGN KEY (game_id) REFERENCES chess.games(id) ON DELETE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_german2_ci;