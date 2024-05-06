import json
import random

from bcrypt import checkpw, hashpw, gensalt
from flask import Flask, jsonify, redirect, render_template, request, abort, url_for, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import login_required, logout_user, login_user, current_user, LoginManager, UserMixin
from flask_bcrypt import Bcrypt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///db.sqlite")
Session = sessionmaker(bind=engine)
session = Session()

app = Flask(__name__)
app.secret_key = "supersecretword"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

TOTAL_CITY = 5


@login_manager.user_loader
def load_user(id):
    return Users.query.filter_by(id=id).first()


# Users
class Users(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    account_type = db.Column(db.String, nullable=False)  # player, or admin

    def __init__(self, username, name, password, account_type):
        self.username = username
        self.name = name
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')  # hashed
        self.account_type = account_type

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)  # hashed password check

    def get_id(self):
        return str(self.id)


class City(db.Model):
    __tablename__ = 'city'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


class Leaderboard(db.Model):
    __tablename__ = 'leaderboard'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('Users', backref=db.backref('scores', lazy=True))

    def __init__(self, user_id, score):
        self.user_id = user_id
        self.score = score


# API routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = Users.query.filter_by(username=username).first()

        if user != None and username == user.username and checkpw(password.encode('utf-8'),
                                                                  user.password.encode('utf-8')):
            login_user(user)
            return redirect('/')

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        name = request.form['name']

        if not (3 <= len(username) <= 20 and 3 <= len(password) <= 20):
            return render_template('register.html', error='Username and password must be between 3 to 20 characters')

        if Users.query.filter_by(username=username).first():
            return render_template('register.html', error='User already exists')

        new_user = Users(username=username, password=password, name=name, account_type=role)

        db.session.add(new_user)
        db.session.commit()

        return redirect('/login')

    return render_template('register.html')


@app.route('/dashboard', methods=['GET'])
def dashboard():
    return render_template('dashboard.html')


@app.route('/')
@login_required
def home():
    if current_user.account_type == "player":
        return redirect('/dashboard')
    if current_user.account_type == "admin":
        return redirect('/admin')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


@app.route('/start_game')
@login_required
def start_game():

    add_random_cities()

    cities = City.query.all()
    random_city = random.choice(cities)
    city_count = City.query.count()

    return render_template('map.html', random_city=random_city, score=TOTAL_CITY - city_count, total_cities=TOTAL_CITY)


@app.route('/view_leaderboard')
@login_required
def view_leaderboard():
    render_template('leaderboard.html')
    scores = Leaderboard.query.order_by(Leaderboard.score.desc()).all()
    print(scores)
    return render_template('leaderboard.html', scores=scores)


@app.route("/map")
@login_required
def map():
    # Check city count after deletion
    city_count = City.query.count()
    if city_count == 0:
        # return render_template('leaderboard.html')
        return redirect('/view_leaderboard')

    add_random_cities()
    cities = City.query.all()
    random_city = random.choice(cities)

    cities_list = []
    for city in cities:
        o = {}
        o["name"] = city.name
        o["latitude"] = city.latitude
        o["longitude"] = city.longitude

        cities_list.append(o)
    print(json.dumps(cities_list))

    return render_template('map.html', random_city=random_city, cities=json.dumps(cities_list), total_cities=TOTAL_CITY)


@app.route('/restart')
@login_required
def restart():
    add_random_cities()
    return redirect('/map')


@app.route('/delete_city', methods=['POST'])
def delete_city():
    city_id = request.form.get('city_id')
    isCorrect = request.form.get('isCorrect')
    # Delete the city with the given ID from the database
    City.query.filter_by(id=city_id).delete()

    # Commit the changes to the database
    db.session.commit()

    if isCorrect == "true":
        # Increment the user's score if the click was correct
        current_user.score += 1
        db.session.commit()  # Commit score change to the database

    return "Deleted city successfully"


@app.route('/scores', methods=['POST'])
def create_score():
    user_id = current_user.id
    score = request.form.get('score')

    if not user_id or not score:
        return jsonify({'error': 'Missing user_id or score'}), 400

    try:
        new_score = Leaderboard(user_id=user_id, score=score)
        db.session.add(new_score)
        db.session.commit()
        return jsonify({'message': 'Score added successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/scores', methods=['GET'])
def get_scores():
    user_id = request.args.get('user_id')
    if user_id:
        scores = Leaderboard.query.filter_by(user_id=user_id).all()
    else:
        scores = Leaderboard.query.all()

    return jsonify(
        [{'id': score.id, 'user_id': score.user_id, 'score': score.score, 'date': score.date} for score in scores]), 200


@app.route('/scores/<int:score_id>', methods=['PUT'])
def update_score(score_id):
    score_data = Leaderboard.query.get(score_id)
    if not score_data:
        return jsonify({'error': 'Score not found'}), 404

    score = request.form.get('score')
    if score:
        score_data.score = score
        db.session.commit()
        return jsonify({'message': 'Score updated successfully'}), 200
    else:
        return jsonify({'error': 'No score provided'}), 400


@app.route('/scores/<int:score_id>', methods=['DELETE'])
def delete_score(score_id):
    score = Leaderboard.query.get(score_id)
    if not score:
        return jsonify({'error': 'Score not found'}), 404

    db.session.delete(score)
    db.session.commit()
    return jsonify({'message': 'Score deleted successfully'}), 200


def add_random_cities():
    # city
    cities_data = [
        {"name": "New York", "latitude": 40.7128, "longitude": -74.0060},
        {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
        {"name": "Tokyo", "latitude": 35.6895, "longitude": 139.6917},
        {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
        {"name": "Los Angeles", "latitude": 34.0522, "longitude": -118.2437},
        {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964},
        {"name": "Beijing", "latitude": 39.9042, "longitude": 116.4074},
        {"name": "Dubai", "latitude": 25.2769, "longitude": 55.2962},
        {"name": "Merced", "latitude": 37.3022, "longitude": -120.4829},
        {"name": "Sydney", "latitude": -33.8688, "longitude": 151.2093},
        {"name": "Mumbai", "latitude": 19.0760, "longitude": 72.8777},
        {"name": "Toronto", "latitude": 43.65107, "longitude": -79.347015},
        {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050},
        {"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176},
        {"name": "Rio de Janeiro", "latitude": -22.9068, "longitude": -43.1729},
        {"name": "Cape Town", "latitude": -33.9249, "longitude": 18.4241},
        {"name": "Singapore", "latitude": 1.3521, "longitude": 103.8198},
        {"name": "Mexico City", "latitude": 19.4326, "longitude": -99.1332},
        {"name": "Seoul", "latitude": 37.5665, "longitude": 126.9780},
        {"name": "Stockholm", "latitude": 59.3293, "longitude": 18.0686},
        {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784},
        {"name": "Lagos", "latitude": 6.5244, "longitude": 3.3792},
        {"name": "Sydney", "latitude": -33.8688, "longitude": 151.2093},
        {"name": "Bangkok", "latitude": 13.7563, "longitude": 100.5018},
        {"name": "Nairobi", "latitude": -1.2864, "longitude": 36.8172},
        {"name": "Vancouver", "latitude": 49.2827, "longitude": -123.1207},
        {"name": "Buenos Aires", "latitude": -34.6037, "longitude": -58.3816},
        {"name": "Chicago", "latitude": 41.8781, "longitude": -87.6298}

    ]
    City.query.delete()
    db.session.commit()

    random.shuffle(cities_data)
    # pick 10 random cities
    selected_cities = cities_data[:10]
    # add cities
    for city_data in selected_cities:
        city = City.query.filter_by(name=city_data["name"]).first()
        if not city:
            new_city = City(name=city_data['name'], latitude=city_data['latitude'],
                            longitude=city_data['longitude'])
            db.session.add(new_city)

    db.session.commit()

    global TOTAL_CITY
    TOTAL_CITY = City.query.count()


# Flask Admin config
admin = Admin(app, name='Admin Panel')
admin.add_view(ModelView(Users, db.session))
admin.add_view(ModelView(City, db.session))
admin.add_view(ModelView(Leaderboard, db.session))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Users.query.filter_by(username='admin').first():
            admin_user = Users(username='admin', name='Admin', password='123', account_type='admin')
            db.session.add(admin_user)
            db.session.commit()

        # Add Players
        players_data = [
            {"username": "jose_santos", "name": "Jose Santos", "password": "123"},
            {"username": "betty_brown", "name": "Betty Brown", "password": "123"},
            {"username": "john_stuart", "name": "John Stuart", "password": "123"},
            {"username": "li_cheng", "name": "Li Cheng", "password": "123"},
            {"username": "nancy_little", "name": "Nancy Little", "password": "123"},
            {"username": "mindy_norris", "name": "Mindy Norris", "password": "123"},
            {"username": "aditya_ranganath", "name": "Aditya Ranganath", "password": "123"},
            {"username": "yi_wen_chen", "name": "Yi Wen Chen", "password": "123"}
        ]

        for player_data in players_data:
            player = Users.query.filter_by(username=player_data["username"]).first()
            if not player:
                new_player = Users(
                    username=player_data["username"],
                    name=player_data["name"],
                    password=player_data["password"],
                    account_type='player'
                )
                db.session.add(new_player)

        add_random_cities()

    app.run(debug=True)
