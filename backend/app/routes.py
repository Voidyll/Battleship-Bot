import sys

sys.path.append("../")

from flask import Blueprint, request, jsonify
import app.validate as validate
import app.services.gameLogic as gameLogic
import AI.agent as ai



import game.game as g;

app = Blueprint('game_api', __name__)

def init_routes(agent: ai.Agent):
    @app.route("/api/game/new", methods=["POST"])
    def createGame():
        game = g.Game()

        agent.place_all_ships(board=game.boards[2])

        return game.to_snapshot(), 200, {'Content-Type': 'application/json'}

    @app.route("/api/game/place-ship", methods=["POST"])
    def placeShip():
        data = request.get_json(silent=True)

        return gameLogic.placeShip(data)

    @app.route("/api/game/fire", methods=["POST"])
    def fire():
        data = request.get_json(silent=True)

        return gameLogic.fire(data, agent)

    @app.route("/api/game/state", methods=["GET"])
    def getState():
        return "<p>Current game state</p>"
    
    return app
