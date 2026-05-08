import os, io, qrcode, base64, psycopg2, psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'jtdi_asset_tracker_final_2026' [cite: 62]
app.permanent_session_lifetime = timedelta(hours=8)

DATABASE_URL = os.environ.get('DATABASE_URL') [cite: 62]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL) [cite: 62]

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session.update({'user': user['username'], 'full_name': user['full_name'], 'role': user['role']})
            cur.execute("INSERT INTO login_logs (full_name, email) VALUES (%s, %s)", (user['full_name'], user['email']))
            conn.commit(); cur.close(); conn.close()
            return redirect(url_for('index'))
        flash("Invalid Credentials."); cur.close(); conn.close()
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login')) [cite: 62]
    search = request.args.get('search', '').strip() [cite: 62]
    category = request.args.get('category', '').strip() [cite: 62]
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) [cite: 62]
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
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']), [cite: 62]
        'maint': len([r for r in data if r['status'] == 'Maintenance']), [cite: 62]
        'faulty': len([r for r in data if r['status'] == 'Faulty']) [cite: 62]
    }
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=search, c_filter=category) [cite: 62]

@app.route('/view/<int:id>')
def view_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,)) [cite: 62]
    asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('asset.html', data=asset) [cite: 53]

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        cur.execute("UPDATE assets SET asset_type=%s, cpu_name=%s, ram_size=%s, storage_type=%s, status=%s, location=%s WHERE id=%s",
                    (request.form.get('asset_type'), request.form.get('cpu_name'), request.form.get('ram_size'), 
                     request.form.get('storage_type'), request.form.get('status'), request.form.get('location'), id))
        conn.commit(); cur.close(); conn.close()
        return redirect(url_for('index'))
    cur.execute("SELECT * FROM assets WHERE id = %s", (id,))
    asset = cur.fetchone(); cur.close(); conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = %s", (id,)) [cite: 62]
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('index')) [cite: 62]

@app.route('/qr/<int:id>')
def qr_code(id):
    qr_url = url_for('view_asset', id=id, _external=True) [cite: 62]
    img = qrcode.make(qr_url) [cite: 62]
    buf = io.BytesIO(); img.save(buf) [cite: 62]
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8') [cite: 62]
    return render_template('qr_display.html', qr_code=qr_b64, id=id) [cite: 62]

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login')) [cite: 62]
