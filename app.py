@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets ORDER BY id DESC')
    data = cur.fetchall()
    
    # NEW: Updated counters for the three statuses
    total = len(data)
    working = len([r for r in data if r['status'] == 'Working'])
    maintenance = len([r for r in data if r['status'] == 'Maintenance'])
    faulty = len([r for r in data if r['status'] == 'Faulty'])
    
    cur.close()
    conn.close()
    return render_template('assets.html', data=data, total=total, 
                           working=working, maintenance=maintenance, faulty=faulty)

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
                    headers={"Content-Disposition": "attachment;filename=assets_report.csv"})
