import os, io, qrcode, base64, psycopg2, psycopg2.extras, pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'jtdi_secure_master_2026'
app.permanent_session_lifetime = timedelta(hours=8)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT, 
        serial_number TEXT UNIQUE, ram_size TEXT, storage_type TEXT, location TEXT, 
        status TEXT, is_deleted BOOLEAN DEFAULT FALSE);''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, full_name TEXT, username TEXT UNIQUE NOT NULL, 
        email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'User');''')
    cur.execute('''CREATE TABLE IF NOT EXISTS login_logs (
        id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
    conn.commit(); cur.close(); conn.close()

init_db()

# --- 1. DASHBOARD & ASSETS ---
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    s, c = request.args.get('search', '').strip(), request.args.get('category', '').strip()
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if session.get('role') != 'Admin': query += " AND is_deleted = FALSE"
    if s:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{s}%', f'%{s}%', f'%{s}%'])
    if c:
        query += " AND asset_type = %s"; params.append(c)
    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()
    stats = {'total': len(data), 'working': len([r for r in data if r['status'] == 'Working']), 'maint': len([r for r in data if r['status'] == 'Maintenance']), 'faulty': len([r for r in data if r['status'] == 'Faulty'])}
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=s, c_filter=c)

# --- 2. USER MANAGEMENT (FIXED ERROR) ---
@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        pw = generate_password_hash(request.form.get('password'))
        try:
            cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", 
                        (request.form.get('full_name'), request.form.get('username'), request.form.get('email'), pw, request.form.get('role')))
            conn.commit()
            flash("User created successfully.")
        except:
            conn.rollback()
            flash("Error: Username or Email already exists.")
            
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    # CRITICAL: Variable name must be 'users' to match the HTML loop
    users_data = cur.fetchall() 
    cur.close(); conn.close()
    return render_template('manage_users.html', users=users_data)

@app.route('/admin/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (id,))
    u = cur.fetchone()
    if u and u[0] != session.get('user'):
        cur.execute("DELETE FROM users WHERE id = %s", (id,))
        conn.commit()
        flash("User deleted.")
    else:
        flash("Cannot delete yourself.")
    cur.close(); conn.close()
    return redirect(url_for('manage_users'))

# --- 3. OTHER ACTIONS (Edit, View, QR, Delete, Logs, Export) ---
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        cur.execute("""UPDATE assets SET asset_type=%s, tracking_number=%s, cpu_name=%s, ram_size=%s, storage_type=%s, location=%s, status=%s WHERE id=%s""", 
                    (request.form.get('asset_type'), request.form.get('tracking_number'), request.form.get('cpu_name'), request.form.get('ram_size'), request.form.get('storage_type'), request.form.get('location'), request.form.get('status'), id))
        conn.commit(); cur.close(); conn.close(); return redirect(url_for('index'))
    cur.execute("SELECT * FROM assets WHERE id = %s", (id,)); asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/admin/logs')
def view_logs():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor); cur.execute("SELECT * FROM login_logs ORDER BY login_time DESC LIMIT 500"); logs = cur.fetchall(); cur.close(); conn.close(); return render_template('login_logs.html', logs=logs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.clear()
        email = request.form.get('email', '').strip().lower()
        conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor); cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if user and check_password_hash(user['password'], request.form.get('password')):
            session.update({'user': user['username'], 'role': user['role'], 'full_name': user['full_name']}); cur.execute("INSERT INTO login_logs (full_name, email) VALUES (%s, %s)", (user['full_name'], user['email'])); conn.commit(); cur.close(); conn.close(); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
