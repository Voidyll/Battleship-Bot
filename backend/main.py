from flask import Flask
import sys

from app.routes import init_routes

sys.path.append("../")

import AI.agent as ai;

app = Flask(__name__)

agent = ai.Agent()

agent.load("../AI/checkpoints/final_model")

app.register_blueprint(init_routes(agent))

if __name__ == "__main__":
    app.run(debug=True)