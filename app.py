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

# --- 1. LOGIN (FIXED ERROR) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Clear any existing session data to prevent conflict
        session.clear()
        
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # We query by email to find the user
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        # Use check_password_hash for secure comparison
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            
            # Record the successful login
            cur.execute("INSERT INTO login_logs (full_name, email) VALUES (%s, %s)", 
                        (user['full_name'], user['email']))
            conn.commit()
            cur.close(); conn.close()
            
            return redirect(url_for('index'))
        else:
            cur.close(); conn.close()
            flash("Invalid email or password. Please try again.")
            
    return render_template('login.html')

# --- 2. DASHBOARD (Function 1 - Protected) ---
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    s, c = request.args.get('search', '').strip(), request.args.get('category', '').strip()
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    
    # Hide deleted assets unless Admin
    if session.get('role') != 'Admin':
        query += " AND is_deleted = FALSE"
        
    if s:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{s}%', f'%{s}%', f'%{s}%'])
    if c:
        query += " AND asset_type = %s"; params.append(c)
        
    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()
    
    # DASHBOARD CALCULATIONS
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=s, c_filter=c)

# --- 3. OTHER ROUTES (Edit, View, QR, Delete, Add, Logs, Users) ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Include your existing routes for edit, view, delete, add, admin/users, admin/logs here...
