import os
import io
import qrcode
import base64
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'jtdi_asset_tracker_final_2026' [cite: 62]

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL') [cite: 62]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL) [cite: 62]

def init_db():
    """Initializes the PostgreSQL database tables if they do not exist."""
    conn = get_db_connection() [cite: 62]
    cur = conn.cursor() [cite: 62]
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
        maintenance_logs TEXT
    );''') [cite: 62]
    conn.commit() [cite: 62]
    cur.close() [cite: 62]
    conn.close() [cite: 62]

# Run database initialization
init_db() [cite: 62]

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple staff login requiring only a username."""
    if request.method == 'POST':
        # Sets the session user to the provided username, defaulting to 'Staff'
        session['user'] = request.form.get('username', 'Staff').strip() [cite: 62]
        return redirect(url_for('index')) [cite: 62]
    return render_template('login.html') [cite: 62]

@app.route('/')
def index():
    """Main dashboard showing statistics and the asset inventory list."""
    if 'user' not in session: 
        return redirect(url_for('login')) [cite: 62]
    
    search = request.args.get('search', '').strip() [cite: 62]
    category = request.args.get('category', '').strip() [cite: 62]
    
    conn = get_db_connection() [cite: 62]
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) [cite: 62]

    # Build the search query
    query = "SELECT * FROM assets WHERE 1=1" [cite: 62]
    params = []

    if search:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)" [cite: 62]
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%']) [cite: 62]
    if category:
        query += " AND asset_type = %s" [cite: 62]
        params.append(category) [cite: 62]

    cur.execute(query + " ORDER BY id DESC", tuple(params)) [cite: 62]
    data = cur.fetchall() [cite: 62]

    # Calculate statistics for the dashboard cards
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']), [cite: 62]
        'maint': len([r for r in data if r['status'] == 'Maintenance']), [cite: 62]
        'faulty': len([r for r in data if r['status'] == 'Faulty']) [cite: 62]
    }
    
    cur.close() [cite: 62]
    conn.close() [cite: 62]
    return render_template('assets.html', data=data, **stats, s_query=search, c_filter=category) [cite: 62]

@app.route('/add', methods=['GET', 'POST'])
def add():
    """Registers new hardware with an automatically generated tracking number."""
    if 'user' not in session: 
        return redirect(url_for('login')) [cite: 62]
        
    if request.method == 'POST':
        conn = get_db_connection() [cite: 62]
        cur = conn.cursor() [cite: 62]
        try:
            # Generate Tracking Number Format: JTDI/SDK/2026/000X
            year = "2026" [cite: 62]
            prefix = f"JTDI/SDK/{year}/" [cite: 62]
            cur.execute("SELECT COUNT(*) FROM assets") [cite: 62]
            count = cur.fetchone()[0] [cite: 62]
            auto_track = f"{prefix}{count + 1:04d}" [cite: 62]

            cur.execute('''INSERT INTO assets 
                (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (
                    request.form.get('asset_type', 'Laptop'), [cite: 62]
                    auto_track, [cite: 62]
                    request.form.get('cpu_name', 'Unknown Model'), [cite: 62]
                    request.form.get('serial_number', 'N/A'), [cite: 62]
                    request.form.get('ram_size', 'N/A'), [cite: 62]
                    request.form.get('storage_type', 'N/A'), [cite: 62]
                    request.form.get('status', 'Working'), [cite: 62]
                    request.form.get('location', 'Sandakan HQ') [cite: 62]
                ))
            conn.commit() [cite: 62]
            return redirect(url_for('index')) [cite: 62]
        except Exception as e:
            conn.rollback() [cite: 62]
            flash(f"Database Error: {e}") [cite: 62]
        finally:
            cur.close() [cite: 62]
            conn.close() [cite: 62]
    return render_template('add.html') [cite: 62]

@app.route('/view/<int:id>')
def view_asset(id):
    """View detailed hardware specifications for a specific asset."""
    conn = get_db_connection() [cite: 62]
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) [cite: 62]
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,)) [cite: 62]
    asset = cur.fetchone() [cite: 62]
    cur.close() [cite: 62]
    conn.close() [cite: 62]
    return render_template('view.html', asset=asset) [cite: 62]

@app.route('/qr/<int:id>')
def qr_code(id):
    """Generates a QR code linking to the specific asset's view page."""
    qr_url = url_for('view_asset', id=id, _external=True) [cite: 62]
    img = qrcode.make(qr_url) [cite: 62]
    buf = io.BytesIO() [cite: 62]
    img.save(buf) [cite: 62]
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8') [cite: 62]
    return render_template('qr_display.html', qr_code=qr_b64, id=id) [cite: 62]

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    """Deletes an asset from the inventory."""
    conn = get_db_connection() [cite: 62]
    cur = conn.cursor() [cite: 62]
    cur.execute("DELETE FROM assets WHERE id = %s", (id,)) [cite: 62]
    conn.commit() [cite: 62]
    cur.close() [cite: 62]
    conn.close() [cite: 62]
    return redirect(url_for('index')) [cite: 62]

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.clear() [cite: 62]
    return redirect(url_for('login')) [cite: 62]

if __name__ == '__main__':
    app.run(debug=True) [cite: 62]
