# DonateSpace https://github.com/tomnudd/DonateSpace

### ### ### ### ### ### ### ### ###
### ### ### # IMPORTS # ### ### ###
### ### ### ### ### ### ### ### ###

from flask import Flask, redirect, url_for
from flask_dance.contrib.google import make_google_blueprint, google
import os
from pymongo import MongoClient

from dotenv import load_dotenv
load_dotenv()

### ### ### ### ### ### ### ### ###
### ### ###  APP SETUP  ### ### ###
### ### ### ### ### ### ### ### ###

# Load environment variables
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
APP_SECRET = os.environ["APP_SECRET"]
DB_URI = os.environ["DB_URI"]

# Create MongoClient instance
client = MongoClient(DB_URI)
db = getattr(client, "DonateSpace")

# Create Flask instance
app = Flask(__name__)
app.secret_key = APP_SECRET

# OAuth2 authentication
blueprint = make_google_blueprint(
    client_id = GOOGLE_CLIENT_ID,
    client_secret = GOOGLE_CLIENT_SECRET,
    scope = "https://www.googleapis.com/auth/userinfo.profile openid https://www.googleapis.com/auth/userinfo.email"
)
app.register_blueprint(blueprint, url_prefix = "/login")

### ### ### ### ### ### ### ### ###
### ### ## DEFINE ROUTES ## ### ###
### ### ### ### ### ### ### ### ###

# Default route
@app.route("/")
def index():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v3/userinfo")
    assert resp.ok, resp.text
    return resp.json()

if __name__ == "__main__":
    app.run()
