from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
import io
import base64
import os

app = Flask(__name__)

# Use an absolute path for the database to avoid errors on Render
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpu_name TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            status TEXT NOT NULL,
            scan_count INTEGER DEFAULT 0,
            last_updated TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

@app.route('/')
def index():
    return render_template('add.html')

@app.route('/assets')
def assets():
    search = request.args.get('search')
    conn = get_db_connection()
    
    # Get stats for the dashboard
    total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    working = conn.execute("SELECT COUNT(*) FROM assets WHERE status='Working'").fetchone()[0]
    faulty = conn.execute("SELECT COUNT(*) FROM assets WHERE status='Faulty'").fetchone()[0]
    
    if search:
        data = conn.execute("SELECT * FROM assets WHERE serial_number LIKE ? OR cpu_name LIKE ?", 
                            ('%'+search+'%', '%'+search+'%')).fetchall()
    else:
        data = conn.execute("SELECT * FROM assets ORDER BY id DESC").fetchall()
    
    conn.close()
    return render_template('assets.html', data=data, total=total, working=working, faulty=faulty)

@app.route('/add', methods=['POST'])
def add():
    cpu_name = request.form['cpu_name']
    serial = request.form['serial']
    status = request.form['status']
    now = datetime.now().strftime("%d-%m-%Y %H:%M")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO assets (cpu_name, serial_number, status, last_updated) VALUES (?, ?, ?, ?)",
                   (cpu_name, serial, status, now))
    asset_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('show_qr', id=asset_id))

@app.route('/qr/<int:id>')
def show_qr(id):
    base_url = "https://asset-tracker-system-o5zl.onrender.com" 
    url = f"{base_url}/asset/{id}"
    qr = qrcode.make(url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return render_template('qr_display.html', img_str=img_str, id=id)

@app.route('/asset/<int:id>')
def asset(id):
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM assets WHERE id=?", (id,)).fetchone()
    if not data:
        return "Asset not found", 404

    new_count = data['scan_count'] + 1
    conn.execute("UPDATE assets SET scan_count=? WHERE id=?", (new_count, id))
    conn.commit()
    data = conn.execute("SELECT * FROM assets WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template('asset.html', data=data, scan=new_count)

@app.route('/export')
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    file_path = "/tmp/asset_report.xlsx" # Use /tmp/ for Render's writeable space
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run()
