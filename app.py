import os
import io
import qrcode
import base64
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'jtdi_secure_system_final_2026'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # --- AUTO-FIX LOGIC ---
    cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='users' AND column_name='email';")
    if cur.fetchone()[0] == 0:
        cur.execute("DROP TABLE IF EXISTS users CASCADE; DROP TABLE IF EXISTS assets CASCADE;")
        conn.commit()

    # --- TABLES ---
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT,
        serial_number TEXT UNIQUE, ram_size TEXT, storage_type TEXT, location TEXT, status TEXT
    );''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, full_name TEXT, username TEXT UNIQUE NOT NULL, 
        email TEXT, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'User'
    );''')
    
    # --- ADMIN (admin / admin123) ---
    hashed_pw = generate_password_hash('admin123')
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s, %s, %s, %s, %s)", 
                    ('System Administrator', 'admin', 'admin@jtdi.gov.my', hashed_pw, 'Admin'))
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username', '').strip(), request.form.get('password', '').strip()
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session.update({'user': user['username'], 'full_name': user['full_name'], 'role': user['role']})
            return redirect(url_for('index'))
        flash("Invalid Credentials.")
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    search, category = request.args.get('search', '').strip(), request.args.get('category', '').strip()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query, params = "SELECT * FROM assets WHERE 1=1", []
    if search:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if category:
        query += " AND asset_type = %s" ; params.append(category)
    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()
    stats = {'total': len(data), 'working': len([r for r in data if r['status'] == 'Working']),
             'maint': len([r for r in data if r['status'] == 'Maintenance']), 'faulty': len([r for r in data if r['status'] == 'Faulty'])}
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=search, c_filter=category)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = %s", (id,))
    conn.commit(); cur.close(); conn.close()
    flash("Asset deleted successfully.")
    return redirect(url_for('index'))

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        fn, un, em, ro = request.form.get('full_name'), request.form.get('username'), request.form.get('email'), request.form.get('role')
        pw = generate_password_hash(request.form.get('password'))
        try:
            cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", (fn,un,em,pw,ro))
            conn.commit(); flash(f"User {fn} created!")
        except: flash("Username exists!")
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users = cur.fetchall(); cur.close(); conn.close()
    return render_template('manage_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    target = cur.fetchone()
    if target and target['username'] != session['user']:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit(); flash("User removed.")
    cur.close(); conn.close()
    return redirect(url_for('manage_users'))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM assets"); count = cur.fetchone()[0]
        track = f"JTDI/SDK/2026/{count + 1:04d}"
        cur.execute('''INSERT INTO assets (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (request.form.get('asset_type'), track, request.form.get('cpu_name'), 
                    request.form.get('serial_number'), request.form.get('ram_size'), request.form.get('storage_type'), 
                    request.form.get('status'), request.form.get('location')))
        conn.commit(); cur.close(); conn.close()
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
