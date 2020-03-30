# DonateSpace https://github.com/tomnudd/DonateSpace

### ### ### ### ### ### ### ### ###
### ### ### # IMPORTS # ### ### ###
### ### ### ### ### ### ### ### ###

from flask import Flask, redirect, url_for, render_template
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
    except Exception as e:
        oauth = OAuth(user_id=user_id, provider="google", token=token)
 
    print(oauth.user)
    if oauth.user:
        login_user(oauth.user)

    else:
        user = User()
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

def getCoordinates(address):
    if address and len(address) > 3:
        rsp = gmaps.geocode(address)
        return rsp

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()
    db.session.commit()

if __name__ == "__main__":
    app.run()
