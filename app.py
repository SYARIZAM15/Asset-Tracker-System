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
app.secret_key = 'jpkn_secure_key' # Keep this secret

# --- ADMINISTRATIVE SECURITY (LOGIN) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id == "1" else None

# --- DATABASE CONNECTION ---
# This pulls the link you pasted in Render settings automatically
DB_URL = os.environ.get('DATABASE_URL') 

def get_db_connection():
    # Connects to your PostgreSQL link: postgresql://asset_tracker_3bs9_user...
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Table includes RAM, Storage, Location, and Category for JPKN tasks
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

# Helper to convert database rows to dictionaries for HTML display
def row_to_dict(cur, row):
    if row is None: return None
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))

# --- AUTH ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Default credentials for JPKN Admin[cite: 1]
        if request.form['username'] == 'admin' and request.form['password'] == 'jpkn123':
            login_user(User("1"))
            return redirect(url_for('assets'))
        flash('Invalid Credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- MAIN INVENTORY DASHBOARD (With Filtering) ---
@app.route('/assets')
@login_required
def assets():
    st_filter = request.args.get('status')
    loc_filter = request.args.get('location')
    search = request.args.get('search')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Calculate Summary Stats for Dashboard[cite: 1]
    cur.execute("SELECT COUNT(*) FROM assets")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM assets WHERE status='Working'")
    working = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM assets WHERE status='Faulty'")
    faulty = cur.fetchone()[0]
    
    # Filtering Logic[cite: 1]
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
    data = [row_to_dict(cur, r) for r in rows]
    
    # Get unique locations for dropdown[cite: 1]
    cur.execute("SELECT DISTINCT location FROM assets")
    locs = [r[0] for r in cur.fetchall() if r[0]]
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, locations=locs, total=total, working=working, faulty=faulty)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        cpu = request.form['cpu_name']
        sn = request.form['serial']
        st = request.form['status']
        ram = request.form['ram']
        store = request.form['storage']
        loc = request.form['location']
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO assets (cpu_name,serial_number,status,ram_size,storage_type,location,last_updated) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                    (cpu, sn, st, ram, store, loc, now))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('assets'))
    return render_template('add.html')

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
        # Create History Log[cite: 1]
        new_hist = f"{old}\n[{now} | {cat}] {log}" if log else old
        
        cur.execute("UPDATE assets SET status=%s, ram_size=%s, storage_type=%s, location=%s, category=%s, maintenance_logs=%s, last_updated=%s WHERE id=%s",
                    (st, ram, store, loc, cat, new_hist, now, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('assets'))

    cur.execute("SELECT * FROM assets WHERE id=%s", (id,))
    asset = row_to_dict(cur, cur.fetchone())
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/asset/<int:id>')
def asset(id):
    # This route is public for scanning QR codes
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM assets WHERE id=%s", (id,))
    data = row_to_dict(cur, cur.fetchone())
    
    if data:
        # Increment scan count[cite: 1]
        cnt = (data.get('scan_count') or 0) + 1
        cur.execute("UPDATE assets SET scan_count=%s WHERE id=%s", (cnt, id))
        conn.commit()
        data['scan_count'] = cnt
    
    cur.close()
    conn.close()
    return render_template('asset.html', data=data)

@app.route('/qr/<int:id>')
@login_required
def show_qr(id):
    # Automated QR Label Printing Logic[cite: 1]
    base_url = "https://asset-tracker-system-o5zl.onrender.com" 
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

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assets'))

if __name__ == '__main__':
    app.run()
