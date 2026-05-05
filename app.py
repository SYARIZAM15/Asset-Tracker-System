from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from datetime import datetime
import qrcode
import io
import base64
import pandas as pd
import sqlite3

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
DB_URL = os.environ.get('DATABASE_URL') 

def get_db_connection():
    if DB_URL:
        import psycopg2
        conn = psycopg2.connect(DB_URL, sslmode='require')
        return conn
    else:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    id_type = "SERIAL PRIMARY KEY" if DB_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS assets (
            id {id_type},
            cpu_name TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            status TEXT NOT NULL,
            ram_size TEXT,
            storage_type TEXT,
            location TEXT,
            maintenance_logs TEXT,
            scan_count INTEGER DEFAULT 0,
            last_updated TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# Helper to fix the missing data issue by converting rows to dictionaries
def row_to_dict(cur, row):
    if row is None: return None
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))

@app.route('/')
def index():
    return render_template('add.html')

@app.route('/assets')
def assets():
    search = request.args.get('search')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM assets")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM assets WHERE status='Working'")
    working = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM assets WHERE status='Faulty'")
    faulty = cur.fetchone()[0]
    
    if search:
        q = "SELECT * FROM assets WHERE serial_number LIKE %s OR cpu_name LIKE %s" if DB_URL else "SELECT * FROM assets WHERE serial_number LIKE ? OR cpu_name LIKE ?"
        cur.execute(q, (f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM assets ORDER BY id DESC")
    
    rows = cur.fetchall()
    data = [row_to_dict(cur, r) for r in rows]
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, total=total, working=working, faulty=faulty)

@app.route('/add', methods=['POST'])
def add():
    cpu = request.form['cpu_name']
    sn = request.form['serial']
    st = request.form['status']
    ram = request.form['ram']
    store = request.form['storage']
    loc = request.form['location']
    now = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    p = "%s,%s,%s,%s,%s,%s,%s" if DB_URL else "?,?,?,?,?,?,?"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"INSERT INTO assets (cpu_name,serial_number,status,ram_size,storage_type,location,last_updated) VALUES ({p})", 
                (cpu, sn, st, ram, store, loc, now))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assets'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    p = "%s" if DB_URL else "?"
    
    if request.method == 'POST':
        st, ram, store, loc = request.form['status'], request.form['ram'], request.form['storage'], request.form['location']
        log, now = request.form['maintenance_logs'], datetime.now().strftime("%d-%m-%Y %H:%M")
        
        cur.execute(f"SELECT maintenance_logs FROM assets WHERE id={p}", (id,))
        old = cur.fetchone()[0] or ""
        new_history = f"{old}\n[{now}] {log}" if log else old
        
        up = "UPDATE assets SET status=%s,ram_size=%s,storage_type=%s,location=%s,maintenance_logs=%s,last_updated=%s WHERE id=%s" if DB_URL else "UPDATE assets SET status=?,ram_size=?,storage_type=?,location=?,maintenance_logs=?,last_updated=? WHERE id=?"
        cur.execute(up, (st, ram, store, loc, new_history, now, id))
        conn.commit()
        return redirect(url_for('assets'))

    cur.execute(f"SELECT * FROM assets WHERE id={p}", (id,))
    asset = row_to_dict(cur, cur.fetchone())
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

@app.route('/asset/<int:id>')
def asset(id):
    conn = get_db_connection()
    cur = conn.cursor()
    p = "%s" if DB_URL else "?"
    cur.execute(f"SELECT * FROM assets WHERE id={p}", (id,))
    data = row_to_dict(cur, cur.fetchone())
    
    if data:
        cnt = (data.get('scan_count') or 0) + 1
        cur.execute(f"UPDATE assets SET scan_count={p} WHERE id={p}", (cnt, id))
        conn.commit()
        data['scan_count'] = cnt
    
    cur.close()
    conn.close()
    return render_template('asset.html', data=data)

@app.route('/qr/<int:id>')
def show_qr(id):
    base_url = "https://asset-tracker-system-o5zl.onrender.com" 
    qr = qrcode.make(f"{base_url}/asset/{id}")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    img = base64.b64encode(buf.getvalue()).decode()
    return render_template('qr_display.html', img_str=img, id=id)

@app.route('/delete/<int:id>')
def delete(id):
    p = "%s" if DB_URL else "?"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM assets WHERE id={p}", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assets'))

if __name__ == '__main__':
    app.run()
