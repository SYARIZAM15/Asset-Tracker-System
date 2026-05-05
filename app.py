from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from datetime import datetime
import qrcode
import io
import base64
import pandas as pd
import psycopg2

app = Flask(__name__)
app.secret_key = 'jpkn_secure_key' # For internship project use only

# --- LOGIN SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id == "1" else None

# --- DATABASE CONFIG ---
DB_URL = os.environ.get('DATABASE_URL') 

def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id SERIAL PRIMARY KEY,
            cpu_name TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            status TEXT NOT NULL,
            ram_size TEXT,
            storage_type TEXT,
            location TEXT,
            maintenance_logs TEXT,
            category TEXT,
            scan_count INTEGER DEFAULT 0,
            last_updated TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- AUTH ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'jpkn123':
            login_user(User("1"))
            return redirect(url_for('assets'))
        flash('Invalid Credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ASSET ROUTES ---
@app.route('/assets')
@login_required
def assets():
    st_filter = request.args.get('status')
    loc_filter = request.args.get('location')
    search = request.args.get('search')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if st_filter:
        query += " AND status = %s"; params.append(st_filter)
    if loc_filter:
        query += " AND location = %s"; params.append(loc_filter)
    if search:
        query += " AND (serial_number LIKE %s OR cpu_name LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    
    cur.execute("SELECT DISTINCT location FROM assets")
    locs = [r[0] for r in cur.fetchall() if r[0]]
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=rows, locations=locs)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        st, ram, store, loc, cat = request.form['status'], request.form['ram'], request.form['storage'], request.form['location'], request.form['category']
        log, now = request.form['maintenance_log'], datetime.now().strftime("%d-%m-%Y %H:%M")
        
        cur.execute("SELECT maintenance_logs FROM assets WHERE id=%s", (id,))
        old = cur.fetchone()[0] or ""
        new_hist = f"{old}\n[{now} | {cat}] {log}" if log else old
        
        cur.execute("UPDATE assets SET status=%s, ram_size=%s, storage_type=%s, location=%s, category=%s, maintenance_logs=%s, last_updated=%s WHERE id=%s",
                    (st, ram, store, loc, cat, new_hist, now, id))
        conn.commit()
        return redirect(url_for('assets'))

    cur.execute("SELECT * FROM assets WHERE id=%s", (id,))
    asset = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/qr/<int:id>')
@login_required
def show_qr(id):
    base_url = "postgresql://asset_tracker_3bs9_user:F8l9wOiXLkqFX3KTK2vYDY6GOXImjtIi@dpg-d7slhk28qa3s73eoh0og-a/asset_tracker_3bs9" 
    qr = qrcode.make(f"{base_url}/asset/{id}")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    img = base64.b64encode(buf.getvalue()).decode()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT serial_number FROM assets WHERE id=%s", (id,))
    sn = cur.fetchone()[0]
    cur.close()
    conn.close()
    return render_template('qr_display.html', img_str=img, id=id, sn=sn)

# Use @login_required for /add and /delete as well
