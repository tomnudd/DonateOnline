# DonateSpace https://github.com/tomnudd/DonateSpace

### ### ### ### ### ### ### ### ###
### ### ### # IMPORTS # ### ### ###
### ### ### ### ### ### ### ### ###

from flask import Flask, redirect, url_for, render_template, request, Response, jsonify
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
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_IP = os.environ["DB_IP"]
MAPS_KEY = os.environ["MAPS_KEY"]

# Create Flask instance
app = Flask(__name__)
app.secret_key = APP_SECRET
login_manager = LoginManager()
login_manager.login_view = "google.login"

# Create database instance
db = SQLAlchemy.create_engine(
    SQLAlchemy.engine.url.URL(
        drivername="mysql+pymysql",
        username=DB_USER,
        password=DB_PASS,
        database="donatespacedb",
        host=DB_IP,
        port=3306
    ),
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    lat = db.Column(db.String, nullable=True)
    lng = db.Column(db.String, nullable=True)

class Item(db.Model):
    iid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    desc = db.Column(db.String, nullable=False)
    id = db.Column(db.String, nullable=False)
    lat = db.Column(db.String, nullable=True)
    lng = db.Column(db.String, nullable=True)
    contact = db.Column(db.String, nullable=False)

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
    if current_user.lat:
        return render_template("explore.html", name=current_user.name, options=True)
    else:
        return render_template("explore.html", name=current_user.name, options=False)

@app.route("/donate", methods=["GET"])
def donate():
    if not current_user.is_authenticated:
        return redirect(url_for("google.login"))
    return render_template("donate.html")
    
@app.route("/receive", methods=["GET"])
def receive():
    if not current_user.is_authenticated:
        return redirect(url_for("google.login"))
    items = Item.query.all()
    near = []
    for item in items:
        if isNear(current_user.lat, current_user.lng, item.lat, item.lng):
            near.append(item)
    return render_template("receive.html", items=near)

@app.route("/api/address", methods=["POST"])
def receiveAddress():
    address = request.form.get("address")
    if not address:
        return jsonify({"Message": "Error"})
    coords = getCoordinates(address)
    if len(coords) == 1:
        pushCoords(coords, current_user.id)
        return redirect(url_for("explore"))
    return jsonify({"Message": "Error"})

@app.route("/donate", methods=["POST"])
def makeDonation():
    name = request.form.get("name")
    desc = request.form.get("desc")
    contact = request.form.get("contact")
    if not name or not desc or not contact:
        return render_template("donate.html", msg="Error")
    pushItem(name, desc, contact, current_user.id, current_user.lat, current_user.lng)
    return render_template("donate.html", msg="Success")

def getCoordinates(address):
    if address and len(address) > 3:
        rsp = gmaps.geocode(address)
        return rsp

# Haversine formula
def isNear(lat1, lon1, lat2, lon2):
    from math import sin, cos, sqrt, atan2, radians

    R = 6373.0

    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c

    # 30km
    if distance < 30:
        return True
    return False


def pushItem(name, desc, contact, id, lat, lng):
    item = Item(name=name, desc=desc, contact=contact, id=id, lat=lat, lng=lng)
    db.session.add_all([item])
    db.session.commit()

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
