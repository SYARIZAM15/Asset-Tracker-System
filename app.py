import os
import io
import qrcode
import base64
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'jtdi_secure_system_2026'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Table 1: Assets
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT,
        serial_number TEXT UNIQUE, ram_size TEXT, storage_type TEXT, location TEXT, 
        status TEXT
    );''')
    # Table 2: Users (Role-Based)
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, 
        username TEXT UNIQUE NOT NULL, 
        password TEXT NOT NULL, 
        role TEXT NOT NULL DEFAULT 'User'
    );''')
    
    # Auto-create Master Admin on first run
    # Username: admin | Password: admin123
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", 
                    ('admin', hashed_pw, 'Admin'))
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        
        flash("Invalid Credentials. Please try again.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN: USER MANAGEMENT ---

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if 'user' not in session or session.get('role') != 'Admin':
        return "Access Denied: Admins Only", 403
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        new_user = request.form.get('username').strip()
        new_pass = generate_password_hash(request.form.get('password').strip())
        new_role = request.form.get('role')
        
        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (new_user, new_pass, new_role))
            conn.commit()
            flash(f"Account for {new_user} created successfully!")
        except:
            conn.rollback()
            flash("Error: Username already exists.")

    cur.execute("SELECT id, username, role FROM users ORDER BY id ASC")
    user_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_users.html', users=user_list)

# --- ASSET MANAGEMENT ---

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if search:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if category:
        query += " AND asset_type = %s"
        params.append(category)

    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()

    # Dashboard Stats logic
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, role=session.get('role'), **stats, s_query=search, c_filter=category)

# (Other asset routes: /add, /edit, /view, /qr, /delete remain same as previous version)

if __name__ == '__main__':
    app.run(debug=True)
