#
# Web based GUI for Clemens chess engine
#

# packages
from flask import Flask
from flask import render_template
from flask import request
import chess
import chess.engine
import chess.pgn
import io
import random
import threading

# create web app instance
app = Flask(__name__)


class Engine:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.engine = None
        self.__start_engine__()

    def __start_engine__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)

    def analyse(self, *args, **kwargs):
        try:
            self.lock.acquire()
            # restart if needed
            if not self.engine:
                self.__start_engine__()
            return self.engine.analyse(*args, **kwargs)
        except:
            self.engine.quit()
            self.engine = None
        finally:
            self.lock.release()


engine = Engine("./engine/clemens")


# probe book move
def probe_book(pgn):
    # open book file
    with open("./engine/book.txt") as f:
        # read book games
        book = f.read()

        # init board
        board = chess.Board()

        # define response moves
        response_moves = []

        # loop over book lines
        for line in book.split("\n")[0:-1]:
            # define variation
            variation = []

            # loop over line moves
            for move in line.split():
                variation.append(chess.Move.from_uci(move))

            # parse variation to SAN
            san = board.variation_san(variation)

            # match book line line
            if pgn in san:
                try:
                    # black move
                    if san.split(pgn)[-1].split()[0][0].isdigit():
                        response_moves.append(san.split(pgn)[-1].split()[1])

                    # white move
                    else:
                        response_moves.append(san.split(pgn)[-1].split()[0])

                except:
                    pass

            # engine makes first move
            if pgn == "":
                response_moves.append(san.split("1. ")[-1].split()[0])

        # return random response move
        if len(response_moves):
            print("BOOK MOVE:", random.choice(response_moves))
            return random.choice(response_moves)

        else:
            return 0


# root(index) route
@app.route("/")
def root():
    return render_template("clemens.html")


# make move API
@app.route("/make_move", methods=["POST"])
def make_move():
    # extract FEN string from HTTP POST request body
    pgn = request.form.get("pgn")

    # probe opening book
    if probe_book(pgn):
        return {"score": "book move", "best_move": probe_book(pgn)}

    # read game moves from PGN
    game = chess.pgn.read_game(io.StringIO(pgn))

    # init board
    board = game.board()

    # loop over moves in game
    for move in game.mainline_moves():
        # make move on chess board
        board.push(move)

    # extract fixed depth value
    fixed_depth = request.form.get("fixed_depth")

    # extract move time value
    move_time = request.form.get("move_time")

    # if move time is available
    if move_time != "0":
        if move_time == "instant":
            try:
                # search for best move instantly
                info = engine.analyse(board, chess.engine.Limit(time=0.1))
            except:
                info = {}
        else:
            try:
                # search for best move with fixed move time
                info = engine.analyse(board, chess.engine.Limit(time=int(move_time)))
            except:
                info = {}

    # if fixed depth is available
    if fixed_depth != "0":
        try:
            # search for best move instantly
            info = engine.analyse(board, chess.engine.Limit(depth=int(fixed_depth)))
        except:
            info = {}

    try:
        # extract best move from PV
        best_move = info["pv"][0]

        # update internal python chess board state
        board.push(best_move)

        # get best score
        try:
            score = -int(str(info["score"])) / 100

        except:
            score = str(info["score"])

            # inverse score
            if "+" in score:
                score = score.replace("+", "-")

            elif "-" in score:
                score = score.replace("-", "+")

        return {
            "fen": board.fen(),
            "best_move": str(best_move),
            "score": score,
            "depth": info["depth"],
            "pv": " ".join([str(move) for move in info["pv"]]),
            "nodes": info["nodes"],
            "time": info["time"],
        }

    except:
        return {"fen": board.fen(), "score": "#+1"}


# main driver
if __name__ == "__main__":
    # start HTTP server
    app.run(debug=True, threaded=True)
