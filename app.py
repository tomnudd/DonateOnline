import os 

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
APP_SECRET = os.environ["APP_SECRET"]

from flask import Flask, redirect, url_for
from flask_dance.contrib.google import make_google_blueprint, google

app = Flask(__name__)
app.secret_key = APP_SECRET
blueprint = make_google_blueprint(
    client_id = GOOGLE_CLIENT_ID,
    client_secret = GOOGLE_CLIENT_SECRET,
    scope = ["profile", "email"]
)
app.register_blueprint(blueprint, url_prefix = "/login")

@app.route("/")
def index():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v3/userinfo")
    assert resp.ok, resp.text
    return resp.json()

if __name__ == "__main__":
    app.run()
