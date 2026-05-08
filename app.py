import os
import io
import qrcode
import base64
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'jtdi_secure_management_2026'

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create Assets Table
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, 
        asset_type TEXT, 
        tracking_number TEXT, 
        cpu_name TEXT,
        serial_number TEXT UNIQUE, 
        ram_size TEXT, 
        storage_type TEXT, 
        location TEXT, 
        status TEXT
    );''')
    
    # Create Users Table
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, 
        username TEXT UNIQUE NOT NULL, 
        password TEXT NOT NULL, 
        role TEXT NOT NULL DEFAULT 'User'
    );''')
    
    # ADMIN RESET LOGIC: Ensures 'admin' exists and has a hashed password
    hashed_pw = generate_password_hash('admin123')
    cur.execute("SELECT password FROM users WHERE username = 'admin'")
    row = cur.fetchone()
    
    if not row:
        # Admin doesn't exist, create it
        cur.execute("INSERT INTO users (username, password, role) VALUES ('admin', %s, 'Admin')", (hashed_pw,))
    elif not row[0].startswith('scrypt:') and not row[0].startswith('pbkdf2:'):
        # Admin exists but has an old plain-text password, update it to hashed
        cur.execute("UPDATE users SET password = %s WHERE username = 'admin'", (hashed_pw,))
    
    conn.commit()
    cur.close()
    conn.close()

# Initialize DB on startup
init_db()

# --- AUTHENTICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        # check_password_hash compares the typed password with the hashed one in DB
        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            flash("Invalid Credentials. Use admin / admin123")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN: USER MANAGEMENT ---

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if 'user' not in session or session.get('role') != 'Admin':
        return "Access Denied", 403
    
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
            flash(f"User {new_user} created!")
        except:
            conn.rollback()
            flash("Username already exists!")

    cur.execute("SELECT id, username, role FROM users ORDER BY id ASC")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_users.html', users=users)

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

    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, role=session.get('role'), **stats, s_query=search, c_filter=category)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM assets")
            count = cur.fetchone()[0]
            track_no = f"JTDI/SDK/2026/{count + 1:04d}"

            cur.execute('''INSERT INTO assets 
                (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (request.form.get('asset_type'), track_no, request.form.get('cpu_name'),
                 request.form.get('serial_number'), request.form.get('ram_size'),
                 request.form.get('storage_type'), request.form.get('status'), request.form.get('location')))
            conn.commit()
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}")
        finally:
            cur.close()
            conn.close()
    return render_template('add.html')

# (Include your /view, /edit, /qr, /delete routes as normal)

if __name__ == '__main__':
    app.run(debug=True)
