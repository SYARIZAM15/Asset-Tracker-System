from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import pandas as pd # Add this to requirements.txt
from datetime import datetime
# ... (keep your existing imports)

# --- NEW: ANALYTICS LOGIC ---
@app.route('/assets')
def assets():
    search = request.args.get('search')
    conn = get_db_connection()
    
    # Get counts for the dashboard
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

# --- NEW: EXPORT TO EXCEL ---
@app.route('/export')
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    
    file_path = "asset_report.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)
