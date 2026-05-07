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
app.secret_key = 'jpkn_asset_tracker_final_2026'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Process 8.0: User Database [cite: 132]
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'User'
    );''')
    # Process 2.0: Asset Database [cite: 42, 137]
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT, 
        ram_size TEXT, storage_type TEXT, serial_number TEXT UNIQUE, location TEXT, 
        status TEXT, is_deleted BOOLEAN DEFAULT FALSE, maintenance_logs TEXT
    );''')
    # Process 7.0: Log Database [cite: 5, 34]
    cur.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
        id SERIAL PRIMARY KEY, username TEXT, action TEXT, tracking_number TEXT, 
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

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
        user_input = request.form['username'].strip()
        role = 'Admin' if user_input.lower() == 'admin' else 'User' [cite: 151, 152]
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (user_input,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (username, role) VALUES (%s, %s)", (user_input, role))
            conn.commit()
        
        session['user'], session['role'] = user_input, role
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Perspective Logic [cite: 152]
    if session.get('role') == 'Admin':
        query = "SELECT * FROM assets WHERE 1=1"
        params = []
    else:
        query = "SELECT * FROM assets WHERE is_deleted = FALSE"
        params = []

    if search:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if category:
        query += " AND asset_type = %s"
        params.append(category)

    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()

    # Dashboard Counts (Process 5.0) [cite: 46, 91]
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working' and not r['is_deleted']]),
        'maint': len([r for r in data if r['status'] == 'Maintenance' and not r['is_deleted']]),
        'faulty': len([r for r in data if r['status'] == 'Faulty' and not r['is_deleted']])
    }
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, role=session.get('role'), **stats, s_query=search, c_filter=category)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT tracking_number FROM assets WHERE id = %s", (id,))
    track_no = cur.fetchone()[0]
    cur.execute("UPDATE assets SET is_deleted = TRUE WHERE id = %s", (id,))
    conn.commit()
    log_activity("SOFT_DELETE", track_no)
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/logs')
def view_logs():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

# ... (Add/Edit/Export/QR routes remain the same as previously provided)
