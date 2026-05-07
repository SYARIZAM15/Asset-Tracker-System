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

# Get database URL from environment variable (Render)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # --- SCHEMA AUTO-UPDATE SECTION ---
    # This ensures old databases get the new columns required for the DFD logic
    try:
        cur.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS asset_type TEXT;")
        cur.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS tracking_number TEXT;")
        cur.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS maintenance_logs TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'User';")
        conn.commit()
    except Exception as e:
        print(f"Schema update skipped or not needed: {e}")

    # Process 8.0: User Database
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, 
        username TEXT UNIQUE, 
        password TEXT, 
        role TEXT DEFAULT 'User'
    );''')

    # Process 2.0: Asset Database
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

    # Process 7.0: Log Database
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

# Initialize Database on Startup
init_db()

# HELPER: Record actions to Log Database (Process 7.0)
def log_activity(action, track_no):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO activity_logs (username, action, tracking_number) VALUES (%s, %s, %s)",
                    (session.get('user'), action, track_no))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Logging failed: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form['username'].strip()
        
        # Determine Role (Process 1.0)
        role = 'Admin' if user_input.lower() == 'admin' else 'User'
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Ensure user exists in the User Database (Process 8.0)
        cur.execute("SELECT * FROM users WHERE username = %s", (user_input,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (username, role) VALUES (%s, %s)", (user_input, role))
            conn.commit()
        
        # Explicit Session Setting to avoid syntax errors
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

    # PERSPECTIVE LOGIC (Process 5.0)
    if session.get('role') == 'Admin':
        query = "SELECT * FROM assets WHERE 1=1"
        params = []
    else:
        query = "SELECT * FROM assets WHERE is_deleted = FALSE"
        params = []

    # SEARCH LOGIC (Process 3.0)
    if search:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if category:
        query += " AND asset_type = %s"
        params.append(category)

    cur.execute(query + " ORDER BY id DESC", tuple(params))
    data = cur.fetchall()

    # Calculate Counts for Dashboard
    total = len(data)
    working = len([r for r in data if r['status'] == 'Working' and not r['is_deleted']])
    maint = len([r for r in data if r['status'] == 'Maintenance' and not r['is_deleted']])
    faulty = len([r for r in data if r['status'] == 'Faulty' and not r['is_deleted']])
    
    cur.close()
    conn.close()
    
    return render_template('assets.html', 
                           data=data, 
                           role=session.get('role'),
                           total=total,
                           working=working,
                           maint=maint,
                           faulty=faulty,
                           s_query=search,
                           c_filter=category)

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
            flash(f"Error: {e}")
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
    
    # Process 2.0: Soft Delete for Admin Recovery
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
        return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

@app.route('/qr/<int:id>')
def qr_display(id):
    # Process 4.0: Generate QR Code
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT serial_number, tracking_number FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()
    cur.close()
    conn.close()
    qr_url = url_for('asset_view', id=id, _external=True)
    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', id=id, sn=asset['serial_number'], track_no=asset['tracking_number'], qr_code=qr_b64)

@app.route('/asset/<int:id>')
def asset_view(id):
    # Process 3.0: Search / View Asset
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('asset.html', data=data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
