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
    cities = City.query.all()
    random_city = random.choice(cities)
    return render_template('map.html', random_city=random_city)

@app.route('/view_leaderboard')
@login_required
def view_leaderboard():
    scores = Leaderboard.query.order_by(Leaderboard.score.desc()).all()
    return render_template('leaderboard.html', scores=scores)


@app.route("/map")
@login_required
def map():
    # Check city count after deletion
    city_count = City.query.count()
    if city_count == 0:
        return render_template('leaderboard.html')

    cities = City.query.all()
    random_city = random.choice(cities)

    return render_template('map.html', random_city=random_city, score=4 - city_count)


@app.route('/restart')
@login_required
def restart():
    # city
    cities_data = [
        {"name": "New York", "latitude": 40.7128, "longitude": -74.0060},
        {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
        {"name": "Tokyo", "latitude": 35.6895, "longitude": 139.6917},
        {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    ]

    # add cities
    for city_data in cities_data:
        city = City.query.filter_by(name=city_data["name"]).first()
        if not city:
            new_city = City(name=city_data['name'], latitude=city_data['latitude'],
                            longitude=city_data['longitude'])
            db.session.add(new_city)

    db.session.commit()
    return redirect('/map')


@app.route('/delete_city', methods=['POST'])
def delete_city():
    city_id = request.form.get('city_id')
    print(city_id)  # Print city ID for debugging purposes

    # Delete the city with the given ID from the database
    City.query.filter_by(id=city_id).delete()

    # Commit the changes to the database
    db.session.commit()

    return "Deleted city successfully"


@app.route('/scores', methods=['POST'])
def create_score():
    user_id = request.form.get('user_id')
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

        # city
        cities_data = [
            {"name": "New York", "latitude": 40.7128, "longitude": -74.0060},
            {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
            {"name": "Tokyo", "latitude": 35.6895, "longitude": 139.6917},
            {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
        ]

        # add cities
        for city_data in cities_data:
            city = City.query.filter_by(name=city_data["name"]).first()
            if not city:
                new_city = City(name=city_data['name'], latitude=city_data['latitude'],
                                longitude=city_data['longitude'])
                db.session.add(new_city)

        db.session.commit()

    app.run(debug=True)
