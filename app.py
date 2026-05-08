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

def init_db():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT, serial_number TEXT UNIQUE, ram_size TEXT, storage_type TEXT, location TEXT, status TEXT);''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, full_name TEXT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'User');''')
    cur.execute('''CREATE TABLE IF NOT EXISTS login_logs (id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
    hashed_pw = generate_password_hash('admin123')
    cur.execute("SELECT * FROM users WHERE email = 'admin@jtdi.gov.my'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", ('Admin', 'admin', 'admin@jtdi.gov.my', hashed_pw, 'Admin'))
    conn.commit(); cur.close(); conn.close()

init_db()

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    s = request.args.get('search', '').strip()
    c = request.args.get('category', '').strip()
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query, params = "SELECT * FROM assets WHERE 1=1", []
    if s:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"; params.extend([f'%{s}%', f'%{s}%', f'%{s}%'])
    if c:
        query += " AND asset_type = %s"; params.append(c)
    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()
    stats = {'total': len(data), 'working': len([r for r in data if r['status'] == 'Working']), 'maint': len([r for r in data if r['status'] == 'Maintenance']), 'faulty': len([r for r in data if r['status'] == 'Faulty'])}
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=s, c_filter=c)

@app.route('/view/<int:id>')
def view_asset(id):
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM assets WHERE id = %s", (id,))
    asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('view.html', asset=asset)

@app.route('/qr/<int:id>')
def qr_code(id):
    qr_url = url_for('view_asset', id=id, _external=True)
    img = qrcode.make(qr_url); buf = io.BytesIO(); img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', qr_code=qr_b64)

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        pw = generate_password_hash(request.form.get('password'))
        cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", (request.form.get('full_name'), request.form.get('username'), request.form.get('email'), pw, request.form.get('role')))
        conn.commit()
    cur.execute("SELECT * FROM users ORDER BY id ASC"); users = cur.fetchall(); cur.close(); conn.close()
    return render_template('manage_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') == 'Admin':
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("DELETE FROM users WHERE id = %s AND username != %s", (user_id, session.get('user'))); conn.commit(); cur.close(); conn.close()
    return redirect(url_for('manage_users'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if user and check_password_hash(user['password'], request.form.get('password')):
            session.update({'user': user['username'], 'role': user['role'], 'full_name': user['full_name']})
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
