from flask import Flask
from flask import request
import sys

sys.path.append("../")

import game.game as g;
import AI.agent as ai;

app = Flask(__name__)

agent = ai.Agent()

agent.load("../AI/checkpoints/final_model")

@app.route("/api/game/new", methods=["POST"])
def createGame():
    game = g.Game()

    agent.place_all_ships(board=game.boards[2])

    return game.to_snapshot()

@app.route("/api/game/place-ship", methods=["POST"])
def placeShip():
    data = request.get_json()

    snapshot = data['snapshot']

    player = int(data['player'])
    shipName = data['ship']
    row = int(data['row'])
    col = int(data['col'])
    orientation = int(data['orientation'])

    game = g.Game().from_snapshot(snapshot)


    error = game.place_ship(player, shipName, row, col, orientation)

    if error.get('Success') == False:
        return error

    return game.to_snapshot()

@app.route("/api/game/fire", methods=["POST"])
def fire():
    return "<p>Fired</p>"

@app.route("/api/game/state", methods=["GET"])
def getState():
    return "<p>Current game state</p>"