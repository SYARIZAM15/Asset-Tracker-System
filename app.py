import os
import io
import qrcode
import base64
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime

# Initialize the Flask App
app = Flask(__name__)
app.secret_key = 'jtdi_asset_tracker_2026_final'

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Ensure table exists with all columns
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
    );''')
    conn.commit()
    cur.close()
    conn.close()

# Run DB initialization
init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['user'] = request.form['username'].strip()
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Base Query
    query = "SELECT * FROM assets WHERE 1=1"
    params = []

    # Search Logic
    if search_query:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
    
    # Category Filter Logic
    if category_filter:
        query += " AND asset_type = %s"
        params.append(category_filter)

    query += " ORDER BY id DESC"
    cur.execute(query, tuple(params))
    data = cur.fetchall()

    # Dashboard Statistics
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    
    cur.close()
    conn.close()
    
    return render_template('assets.html', 
                           data=data, 
                           **stats, 
                           s_query=search_query, 
                           c_filter=category_filter)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''INSERT INTO assets (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                        (request.form['asset_type'], request.form['tracking_number'], request.form['cpu_name'], 
                         request.form['serial_number'], request.form['ram_size'], 
                         request.form['storage_type'], request.form['status'], request.form['location']))
            conn.commit()
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}")
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
        cur.execute('''UPDATE assets SET asset_type=%s, tracking_number=%s, cpu_name=%s, ram_size=%s, 
                    storage_type=%s, location=%s, status=%s WHERE id=%s''',
                    (request.form['asset_type'], request.form['tracking_number'], request.form['cpu_name'], 
                     request.form['ram_size'], request.form['storage_type'], request.form['location'], 
                     request.form['status'], id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/view/<int:id>')
def view_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('view.html', asset=asset)

@app.route('/qr/<int:id>')
def qr_code(id):
    qr_url = url_for('view_asset', id=id, _external=True)
    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', qr_code=qr_b64, id=id)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
