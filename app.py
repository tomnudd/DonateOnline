# DonateSpace https://github.com/tomnudd/DonateSpace

### ### ### ### ### ### ### ### ###
### ### ### # IMPORTS # ### ### ###
### ### ### ### ### ### ### ### ###

from flask import Flask, redirect, url_for, render_template, request, Response
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage, OAuthConsumerMixin
from flask_login import current_user, LoginManager, login_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
import json

import googlemaps
import os

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
MAPS_KEY = os.environ["MAPS_KEY"]

# Create Flask instance
app = Flask(__name__)
app.secret_key = APP_SECRET
login_manager = LoginManager()
login_manager.login_view = "google.login"

# Create database instance
db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    lat = db.Column(db.String, nullable=True)
    lng = db.Column(db.String, nullable=True)

class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

# Create Google Maps instance
gmaps = googlemaps.Client(key=MAPS_KEY)

# OAuth2 authentication
blueprint = make_google_blueprint(
    client_id = GOOGLE_CLIENT_ID,
    client_secret = GOOGLE_CLIENT_SECRET,
    scope = "https://www.googleapis.com/auth/userinfo.profile openid https://www.googleapis.com/auth/userinfo.email"
)
blueprint.backend = SQLAlchemyStorage(OAuth, db.session, user=current_user)
app.register_blueprint(blueprint, url_prefix = "/login")

# Set up login manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@oauth_authorized.connect_via(blueprint)
def google_logged_in(blueprint, token):
    if not token:
        return False

    resp = blueprint.session.get("/oauth2/v3/userinfo")
    if not resp.ok:
        return False

    info = resp.json()
    user_id = info["sub"]

    query = OAuth.query.filter_by(user_id=user_id)
    try:
        oauth = query.one()
    except Exception:
        oauth = OAuth(user_id=user_id, provider="google", token=token)
 
    if oauth.user:
        login_user(oauth.user)
    else:
        user = User(name=info["given_name"])
        oauth.user = user
        db.session.add_all([user, oauth])
        db.session.commit()
        login_user(user)

    return False


### ### ### ### ### ### ### ### ###
### ### ## DEFINE ROUTES ## ### ###
### ### ### ### ### ### ### ### ###

# Default route
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/explore", methods=["GET"])
def explore():
    if not current_user.is_authenticated:
        return redirect(url_for("google.login"))
    else:
        if current_user.lat:
            return render_template("explore.html", name=current_user.name, options=True)
        else:
            return render_template("explore.html", name=current_user.name, options=False)

@app.route("/api/address", methods=["POST"])
def receiveAddress():
    address = request.form.get("address")
    if not address:
        return Response("Error")
    coords = getCoordinates(address)
    if len(coords) == 1:
        pushCoords(coords, current_user.id)
        return redirect(url_for("explore"))
    return Response("Error")

def getCoordinates(address):
    if address and len(address) > 3:
        rsp = gmaps.geocode(address)
        return rsp

def pushCoords(coords, id):
    coords = coords[0]["geometry"]["location"]
    user = User.query.filter_by(id=id).first()
    user.lat = coords["lat"]
    user.lng = coords["lat"]
    db.session.commit()

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()
    db.session.commit()

if __name__ == "__main__":
    app.run()
