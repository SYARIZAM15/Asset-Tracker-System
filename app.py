import os
import io
import csv
import base64
import qrcode
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response

app = Flask(__name__)
app.secret_key = 'jpkn_assets_tracking_pro_2026'

# Ensure DATABASE_URL is set in Render Environment Variables
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets ORDER BY id DESC')
    data = cur.fetchall()
    
    # Counters for the dashboard
    total = len(data)
    working = len([r for r in data if r['status'] == 'Working'])
    maintenance = len([r for r in data if r['status'] == 'Maintenance'])
    faulty = len([r for r in data if r['status'] == 'Faulty'])
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, total=total, 
                           working=working, maintenance=maintenance, faulty=faulty)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()

    if request.method == 'POST':
        log_entry = f"{request.form['category']}: {request.form['action']}"
        new_logs = (asset['maintenance_logs'] + "\n" + log_entry) if asset['maintenance_logs'] else log_entry
        
        cur.execute('''UPDATE assets SET cpu_name=%s, ram_size=%s, storage_type=%s, location=%s, status=%s, maintenance_logs=%s 
                    WHERE id=%s''',
                    (request.form['cpu_name'], request.form['ram_size'], request.form['storage_type'], 
                     request.form['location'], request.form['status'], new_logs, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM assets WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export')
def export_assets():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT cpu_name, serial_number, ram_size, storage_type, location, status FROM assets')
    rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['CPU Name', 'Serial Number', 'RAM', 'Storage', 'Location', 'Status'])
    writer.writerows(rows)
    
    return Response(output.getvalue(), mimetype='text/csv', 
                    headers={"Content-Disposition": "attachment;filename=assets_tracking_report.csv"})

# ... (rest of your app.py routes: login, add, asset_view, qr_display) ...
