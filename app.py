import os, io, qrcode, base64, psycopg2, psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'jtdi_asset_tracker_final_2026' [cite: 8]

# Database connection details 
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Get search and category filter values from the URL 
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Build filtered query for the inventory list 
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

    # Calculate statistics for the dashboard cards 
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    
    cur.close(); conn.close()
    return render_template('assets.html', data=data, **stats, s_query=search, c_filter=category)

# Individual routes for managing assets 
@app.route('/view/<int:id>')
def view_asset(id):
    # Retrieve single asset details for the 'View' spec page
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()
    cur.close(); conn.close()
    return render_template('asset.html', data=asset)

@app.route('/qr/<int:id>')
def qr_code(id):
    # Generate QR code linking to the asset's specific view page
    qr_url = url_for('view_asset', id=id, _external=True)
    img = qrcode.make(qr_url)
    buf = io.BytesIO(); img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return render_template('qr_display.html', qr_code=qr_b64, id=id)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    # Remove asset from the database 
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = %s", (id,))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('index'))
