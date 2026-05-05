from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3 # Keep for local testing
import os
from datetime import datetime
import qrcode
import io
import base64

app = Flask(__name__)

# DATABASE CONFIGURATION
# On Render, you will add an Environment Variable named DATABASE_URL
DB_URL = os.environ.get('DATABASE_URL') 

def get_db_connection():
    # If on Render, use PostgreSQL. If local, use SQLite.
    if DB_URL:
        import psycopg2
        conn = psycopg2.connect(DB_URL, sslmode='require')
    else:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Updated table with Hardware Details
    cur.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id SERIAL PRIMARY KEY,
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

# --- ROUTES ---

@app.route('/add', methods=['POST'])
def add():
    cpu_name = request.form['cpu_name']
    serial = request.form['serial']
    status = request.form['status']
    ram = request.form['ram']
    storage = request.form['storage']
    location = request.form['location']
    now = datetime.now().strftime("%d-%m-%Y %H:%M")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (cpu_name, serial_number, status, ram_size, storage_type, location, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (cpu_name, serial, status, ram, storage, location, now))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assets'))

# --- EDIT FEATURE ---
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        status = request.form['status']
        ram = request.form['ram']
        storage = request.form['storage']
        location = request.form['location']
        new_log = request.form['maintenance_logs']
        now = datetime.now().strftime("%d-%m-%Y %H:%M")

        # Append new log to old logs for history
        cur.execute("SELECT maintenance_logs FROM assets WHERE id = %s", (id,))
        old_logs = cur.fetchone()[0] or ""
        updated_logs = f"{old_logs}\n[{now}] {new_log}"

        cur.execute("""
            UPDATE assets 
            SET status=%s, ram_size=%s, storage_type=%s, location=%s, maintenance_logs=%s, last_updated=%s
            WHERE id=%s
        """, (status, ram, storage, location, updated_logs, now, id))
        conn.commit()
        return redirect(url_for('assets'))

    cur.execute("SELECT * FROM assets WHERE id = %s", (id,))
    asset = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)

# --- DELETE FEATURE ---
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assets'))
