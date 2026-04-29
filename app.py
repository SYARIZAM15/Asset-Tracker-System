from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
import qrcode
import io
import base64

app = Flask(__name__)

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cpu_name TEXT,
        serial_number TEXT,
        status TEXT,
        scan_count INTEGER DEFAULT 0,
        last_updated TEXT
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME PAGE ----------------
@app.route('/')
def index():
    return render_template('add.html')

# ---------------- VIEW ALL ASSETS ----------------
@app.route('/assets')
def assets():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM assets")
    data = c.fetchall()

    conn.close()

    return render_template('assets.html', data=data)

# ---------------- ADD ASSET ----------------
@app.route('/add', methods=['POST'])
def add():
    cpu_name = request.form['cpu_name']
    serial = request.form['serial']
    status = request.form['status']

    now = datetime.now().strftime("%d-%m-%Y %H:%M")

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
        INSERT INTO assets (cpu_name, serial_number, status, last_updated)
        VALUES (?, ?, ?, ?)
    """, (cpu_name, serial, status, now))

    asset_id = c.lastrowid

    conn.commit()
    conn.close()

    # ---------------- DYNAMIC QR CODE (NO FILE SAVE) ----------------
    base_url = "https://asset-tracker-system-o5zl.onrender.com"  # CHANGE AFTER DEPLOY
    url = f"{base_url}/asset/{asset_id}"

    qr = qrcode.make(url)

    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")

    img_str = base64.b64encode(buffer.getvalue()).decode()

    return f"""
    <h2>Asset Added Successfully!</h2>
    <p>Scan this QR:</p>
    <img src="data:image/png;base64,{img_str}" width="200">
    <br><br>
    <a href='/'>⬅️ Back</a> | 
    <a href='/assets'>📋 View All Assets</a>
    """

# ---------------- VIEW ASSET ----------------
@app.route('/asset/<int:id>')
def asset(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM assets WHERE id=?", (id,))
    data = c.fetchone()

    if not data:
        return "Asset not found"

    new_count = data[4] + 1

    c.execute("UPDATE assets SET scan_count=? WHERE id=?", (new_count, id))
    conn.commit()
    conn.close()

    return render_template('asset.html', data=data, scan=new_count)

# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    app.run()
