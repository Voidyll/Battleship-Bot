from flask import Flask
from flask import request
import sys
import validate as validate
from validate import Validation

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

    return game.to_snapshot(), 200, {'Content-Type': 'application/json'}

@app.route("/api/game/place-ship", methods=["POST"])
def placeShip():
    validHeaders = {"player", "ship", "row", "col", "orientation"}

    data = request.get_json(silent=True)

    valid = validate.validateInput(data, validHeaders)
    if not valid.success:
        return {'error': 'Did not include all headers...', 'missing-headers': list(valid.missingHeaders)}, 400, {'Content-Type': 'application/json'}

    snapshot = data['snapshot']

    player = int(data['player'])
    shipName = data['ship']
    row = int(data['row'])
    col = int(data['col'])
    orientation = int(data['orientation'])

    game = g.Game().from_snapshot(snapshot)


    error = game.place_ship(player, shipName, row, col, orientation)

    if error.get('Success') == False:
        return error, 400, {'Content-Type': 'application/json'}

    return game.to_snapshot(), 200, {'Content-Type': 'application/json'}

@app.route("/api/game/fire", methods=["POST"])
def fire():
    validHeaders = {"snapshot", "player", "row", "col", "ai_player", "autoResolveAiTurn"}

    data = request.get_json(silent=True)

    valid = validate.validateInput(data, validHeaders)
    if not valid.success:
        return {'error': 'Did not include all headers...', 'missing-headers': list(valid.missingHeaders)}, 400, {'Content-Type': 'application/json'}


    snapshot = data['snapshot']
    player = int(data['player'])
    row = int(data['row'])
    col = int(data['col'])
    ai_player = int(data['ai_player'])
    autoResolveAiTurn = bool(data['autoResolveAiTurn'])

    game = g.Game().from_snapshot(snapshot)

    aiState = game.get_ai_state(player)

    status = game.fire_with_auto_ai_turn(player, row, col, ai_player, agent.choose_shot(ai_state=aiState), autoResolveAiTurn)

    return status, 200, {'Content-Type': 'application/json'}

@app.route("/api/game/state", methods=["GET"])
def getState():
    return "<p>Current game state</p>"
