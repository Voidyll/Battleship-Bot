from flask import Flask, render_template

app = Flask(
    __name__, template_folder="frontend/templates", static_folder="frontend/static"
)


@app.route("/")
def index():
    return render_template("game.html")


if __name__ == "__main__":
    print("Running on localhost:5000")
    app.run(debug=True, port=5000)
