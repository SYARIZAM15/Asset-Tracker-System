import os, io, qrcode, base64, psycopg2, psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'jtdi_secure_master_2026'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    s, c = request.args.get('search', '').strip(), request.args.get('category', '').strip()
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

# --- FIXED VIEW ROUTE ---
@app.route('/view/<int:id>')
def view_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone(); cur.close(); conn.close()
    # Change 'asset.html' to 'view.html' if that is your filename
    return render_template('view.html', asset=asset)

# --- FIXED EDIT ROUTE (Matches your HTML) ---
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        # Get data from your specific form
        cur.execute("""UPDATE assets SET 
            asset_type=%s, tracking_number=%s, cpu_name=%s, 
            ram_size=%s, storage_type=%s, location=%s, status=%s 
            WHERE id=%s""", 
            (request.form.get('asset_type'), request.form.get('tracking_number'),
             request.form.get('cpu_name'), request.form.get('ram_size'),
             request.form.get('storage_type'), request.form.get('location'),
             request.form.get('status'), id))
        conn.commit(); cur.close(); conn.close()
        flash("Asset updated successfully!")
        return redirect(url_for('index'))
    
    cur.execute("SELECT * FROM assets WHERE id = %s", (id,))
    asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('edit.html', asset=asset)

# --- FIXED QR ROUTE ---
@app.route('/qr/<int:id>')
def qr_code(id):
    if 'user' not in session: return redirect(url_for('login'))
    qr_url = url_for('view_asset', id=id, _external=True)
    img = qrcode.make(qr_url)
    buf = io.BytesIO(); img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', qr_code=qr_b64, id=id)

# (Add your /login, /logout, /add, and /admin routes here)
