from flask import Flask
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
    return "<p>Ship Placed</p>"

@app.route("/api/game/fire", methods=["POST"])
def fire():
    return "<p>Fired</p>"

@app.route("/api/game/state", methods=["GET"])
def getState():
    return "<p>Current game state</p>"