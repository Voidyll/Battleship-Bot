import sys

sys.path.append("../")

import game.game as g;
import AI.agent as ai;

def createGame(agent : ai.Agent):
    game = g.Game()

    agent.place_all_ships(self=agent, board=game.boards[2])

    return game.to_snapshot()