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
    
    # Process 8.0: User Database [cite: 59, 131]
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'User'
    );''')

    # Process 2.0: Asset Database with Soft Delete column [cite: 4, 42, 75]
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

    # Process 7.0: Log Database [cite: 5, 50, 112]
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

# Run database initialization
init_db()

# HELPER: Record actions to Log Database (Process 7.0) [cite: 34, 112]
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
        user = request.form['username']
        # Authentication Logic (Process 1.0) [cite: 40, 73, 83]
        # For simplicity, 'admin' username gets Admin role, others get User
        role = 'Admin' if user.lower() == 'admin' else 'User'
        session['user'] = user
        session['role'] = role
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # PERSPECTIVE LOGIC: Admin sees everything; User sees only Active [cite: 147, 151, 152]
    if session.get('role') == 'Admin':
        cur.execute('SELECT * FROM assets ORDER BY id DESC')
    else:
        cur.execute('SELECT * FROM assets WHERE is_deleted = FALSE ORDER BY id DESC')
    
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, role=session.get('role'))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            # --- AUTO-GENERATE TRACKING NUMBER (JTDI/SDK/2026/xxxx) ---
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
            log_activity("REGISTERED_NEW", auto_tracking_no) # Process 7.0 [cite: 34]
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash("Error: Serial Number may already exist!")
        finally:
            cur.close()
            conn.close()
    return render_template('add.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()

    if request.method == 'POST':
        try:
            # Append new maintenance log entry
            log_entry = f"{request.form['category']}: {request.form['action']} ({datetime.now().strftime('%Y-%m-%d')})"
            new_logs = (asset['maintenance_logs'] + "\n" + log_entry) if asset['maintenance_logs'] else log_entry
            
            cur.execute('''UPDATE assets SET asset_type=%s, cpu_name=%s, ram_size=%s, storage_type=%s, location=%s, status=%s, maintenance_logs=%s 
                        WHERE id=%s''',
                        (request.form['asset_type'], request.form['cpu_name'], request.form['ram_size'], 
                         request.form['storage_type'], request.form['location'], request.form['status'], new_logs, id))
            conn.commit()
            log_activity("EDITED_ASSET", asset['tracking_number'])
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash(f"Update Failed: {e}")
        finally:
            cur.close()
            conn.close()
    
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT tracking_number FROM assets WHERE id = %s", (id,))
    track_no = cur.fetchone()[0]

    # SOFT DELETE: Mark as deleted but keep in database for Admin auditing [cite: 1, 4]
    cur.execute("UPDATE assets SET is_deleted = TRUE WHERE id = %s", (id,))
    conn.commit()
    
    log_activity("SOFT_DELETE", track_no) # Process 7.0 [cite: 34]
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/logs')
def view_logs():
    # Process 7.0: Admin-only access to Log Summary [cite: 50, 112, 126]
    if session.get('role') != 'Admin':
        flash("Access Denied: Admins Only.")
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

@app.route('/export')
def export_assets():
    # Process 6.0: Export Data to Excel [cite: 48, 104, 111]
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    # Filter based on role even for export
    if session.get('role') == 'Admin':
        cur.execute('SELECT asset_type, tracking_number, cpu_name, serial_number, location, status FROM assets')
    else:
        cur.execute('SELECT asset_type, tracking_number, cpu_name, serial_number, location, status FROM assets WHERE is_deleted = FALSE')
    
    rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Type', 'Tracking No', 'Brand/Model', 'Serial Number', 'Agency', 'Status'])
    writer.writerows(rows)
    
    log_activity("EXPORTED_CSV", "ALL_RECORDS")
    return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=jpkn_assets_report.csv"})

@app.route('/qr/<int:id>')
def qr_display(id):
    # Process 4.0: Generate QR Code [cite: 44, 79, 103]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT serial_number, tracking_number FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()
    cur.close()
    conn.close()
    
    # Use full external URL so mobile phones can scan it
    qr_url = url_for('asset_view', id=id, _external=True)
    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', id=id, sn=asset['serial_number'], track_no=asset['tracking_number'], qr_code=qr_b64)

@app.route('/asset/<int:id>')
def asset_view(id):
    # Process 3.0: Search / View Asset [cite: 48, 77, 98]
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
