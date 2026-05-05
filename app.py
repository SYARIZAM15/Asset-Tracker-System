import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jpkn_secret_key_2026'

# DATABASE CONNECTION LOGIC
# This automatically fixes the 'postgres://' vs 'postgresql://' issue
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Safe Mode: Helps prevent "Internal Server Error" by checking connection heartbeat
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    status = db.Column(db.String(50))
    location = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('assets'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'jpkn123':
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=password)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('assets'))
        else:
            flash('Invalid JPKN Credentials')
    return render_template('login.html')

@app.route('/assets')
@login_required
def assets():
    all_assets = Asset.query.all()
    return render_template('index.html', assets=all_assets)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_asset():
    if request.method == 'POST':
        new_asset = Asset(
            model=request.form.get('model'),
            serial_number=request.form.get('serial_number'),
            status=request.form.get('status'),
            location=request.form.get('location')
        )
        db.session.add(new_asset)
        db.session.commit()
        return redirect(url_for('assets'))
    return render_template('add.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # This creates the tables in PostgreSQL automatically
    app.run(debug=True)
