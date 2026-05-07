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
    # Process 8.0: User Database [cite: 91, 92]
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'User'
    );''')
    # Process 2.0: Asset Database [cite: 75, 76]
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT, 
        ram_size TEXT, storage_type TEXT, serial_number TEXT UNIQUE, location TEXT, 
        status TEXT, is_deleted BOOLEAN DEFAULT FALSE, maintenance_logs TEXT
    );''')
    # Process 7.0: Log Database [cite: 112, 113]
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
        
        # Fixed syntax logic 
        if user_input.lower() == 'admin':
            role = 'Admin'
        else:
            role = 'User'
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Process 1.0: Check User Database 
        cur.execute("SELECT * FROM users WHERE username = %s", (user_input,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (username, role) VALUES (%s, %s)", (user_input, role))
            conn.commit()
        
        # Explicit Session Setting
        session['user'] = user_input
        session['role'] = role
        
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

    # Process 5.0: Dashboard Generation [cite: 91, 92]
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
    
    # Soft Delete for Recovery/History
    cur.execute("UPDATE assets SET is_deleted = TRUE WHERE id = %s", (id,))
    conn.commit()
    log_activity("SOFT_DELETE", track_no)
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/logs')
def view_logs():
    if session.get('role') != 'Admin': 
        return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

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
            flash("Error processing registration.")
        finally:
            cur.close()
            conn.close()
    return render_template('add.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
