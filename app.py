import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jpkn_sandakan_2026'

# Menggunakan SQLite untuk mengelakkan ralat sambungan PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///assets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Memastikan user ke /login jika tiada akses[cite: 1]

# --- MODELS ---
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

# --- ROUTES ---

@app.route('/')
@login_required # Menyekat akses tanpa login[cite: 1]
def index():
    all_assets = Asset.query.all()
    return render_template('index.html', assets=all_assets)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Log masuk admin JPKN
        if username == 'admin' and password == 'jpkn123':
            user = User.query.filter_by(username='admin').first()
            if not user:
                # Mencipta user admin jika belum wujud dalam database baru
                user = User(username='admin', password='password')
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('ID atau Kata Laluan Salah!')
    return render_template('login.html')

@app.route('/add', methods=['GET', 'POST'])
@login_required # Menyekat akses tanpa login[cite: 1]
def add():
    if request.method == 'POST':
        new_asset = Asset(
            model=request.form.get('model'),
            serial_number=request.form.get('serial_number'),
            status=request.form.get('status'),
            location=request.form.get('location')
        )
        db.session.add(new_asset)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Mencipta fail assets.db secara automatik
    app.run(debug=True)
