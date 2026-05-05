from flask import Flask
import sys
import os

from app.routes import init_routes

sys.path.append("../")

import AI.agent as ai

base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.join(base_dir, "..")

app = Flask(
    __name__,
    template_folder=os.path.join(root_dir, "frontend", "templates"),
    static_folder=os.path.join(root_dir, "frontend", "static"),
)

agent = ai.Agent()

agent.load("../AI/checkpoints/final_model")

app.register_blueprint(init_routes(agent))

if __name__ == "__main__":
    app.run(debug=True)
