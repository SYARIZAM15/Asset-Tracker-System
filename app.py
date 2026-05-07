import os
import io
import csv
import base64
import qrcode
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'jpkn_tracker_2026_pro'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Process 8.0: User Database
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'User'
    );''')

    # Process 2.0: Asset Database (with Soft Delete flag)
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY,
        asset_type TEXT,
        tracking_number TEXT,
        cpu_name TEXT,
        ram_size TEXT,
        storage_type TEXT,
        serial_number TEXT UNIQUE,
        location TEXT,
        status TEXT,
        is_deleted BOOLEAN DEFAULT FALSE,
        maintenance_logs TEXT
    );''')

    # Process 7.0: Log Database (Activity Logs)
    cur.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
        id SERIAL PRIMARY KEY,
        username TEXT,
        action TEXT,
        tracking_number TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''')
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# HELPER: Record actions to Log Database (Process 7.0)
def log_activity(action, track_no):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO activity_logs (username, action, tracking_number) VALUES (%s, %s, %s)",
                (session.get('user'), action, track_no))
    conn.commit()
    cur.close()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        # Simple Logic: If username is 'admin', set as Admin role
        role = 'Admin' if user.lower() == 'admin' else 'User'
        session['user'] = user
        session['role'] = role
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # PERSPECTIVE LOGIC: Admin sees all (History); User sees only Active (Process 5.0)
    if session.get('role') == 'Admin':
        cur.execute('SELECT * FROM assets ORDER BY id DESC')
    else:
        cur.execute('SELECT * FROM assets WHERE is_deleted = FALSE ORDER BY id DESC')
    
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, role=session.get('role'))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            year = "2026"
            prefix = f"JTDI/SDK/{year}/"
            cur.execute("SELECT COUNT(*) FROM assets WHERE tracking_number LIKE %s", (prefix + '%',))
            count = cur.fetchone()[0]
            auto_tracking_no = f"{prefix}{count + 1:04d}"

            cur.execute('''INSERT INTO assets (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                        (request.form['asset_type'], auto_tracking_no, request.form['cpu_name'], 
                         request.form['serial_number'], request.form['ram_size'], 
                         request.form['storage_type'], request.form['status'], request.form['location']))
            
            conn.commit()
            log_activity("REGISTERED_NEW", auto_tracking_no)
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash("S/N Already Exists!")
        finally:
            cur.close()
            conn.close()
    return render_template('add.html')

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT tracking_number FROM assets WHERE id = %s", (id,))
    track_no = cur.fetchone()[0]

    # Process 2.0: Soft Delete for Admin Recovery and Reference
    cur.execute("UPDATE assets SET is_deleted = TRUE WHERE id = %s", (id,))
    conn.commit()
    
    log_activity("SOFT_DELETE", track_no)
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/logs')
def view_logs():
    # Process 7.0: Admin-only access to Log Summary
    if session.get('role') != 'Admin':
        return "Unauthorized", 403
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
