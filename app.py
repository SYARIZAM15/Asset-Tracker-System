import os, io, qrcode, base64, psycopg2, psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
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
        status TEXT, is_deleted BOOLEAN DEFAULT FALSE);''');
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, full_name TEXT, username TEXT UNIQUE NOT NULL, 
        email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'User');''');
    cur.execute('''CREATE TABLE IF NOT EXISTS login_logs (
        id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''');
    conn.commit(); cur.close(); conn.close()

init_db()

# --- 1. DASHBOARD & SEARCH ---
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    s, c = request.args.get('search', '').strip(), request.args.get('category', '').strip()
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "SELECT * FROM assets WHERE 1=1"
    if session.get('role') != 'Admin': query += " AND is_deleted = FALSE"
    params = []
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

# --- 2. USER MANAGEMENT (FIXED & ADDED EDIT/DELETE) ---
@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        pw = generate_password_hash(request.form.get('password'))
        try:
            cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", 
                        (request.form.get('full_name'), request.form.get('username'), request.form.get('email'), pw, request.form.get('role')))
            conn.commit(); flash("User created!")
        except:
            conn.rollback(); flash("Error: Email/Username exists.")
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users_data = cur.fetchall()
    cur.close(); conn.close()
    return render_template('manage_users.html', users=users_data)

@app.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        full_name, email, role = request.form.get('full_name'), request.form.get('email'), request.form.get('role')
        password = request.form.get('password')
        if password:
            hashed_pw = generate_password_hash(password)
            cur.execute("UPDATE users SET full_name=%s, email=%s, role=%s, password=%s WHERE id=%s", (full_name, email, role, hashed_pw, id))
        else:
            cur.execute("UPDATE users SET full_name=%s, email=%s, role=%s WHERE id=%s", (full_name, email, role, id))
        conn.commit(); cur.close(); conn.close(); flash("User updated!"); return redirect(url_for('manage_users'))
    cur.execute("SELECT * FROM users WHERE id = %s", (id,)); user = cur.fetchone(); cur.close(); conn.close()
    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (id,)); conn.commit(); cur.close(); conn.close()
    flash("User deleted!"); return redirect(url_for('manage_users'))

# --- 3. OTHER CORE FUNCTIONS ---
@app.route('/view/<int:id>')
def view_asset(id):
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM assets WHERE id = %s", (id,)); asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('view.html', asset=asset)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        u = cur.fetchone()
        if u and check_password_hash(u['password'], request.form.get('password')):
            session.update({'user': u['username'], 'role': u['role'], 'full_name': u['full_name']})
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
