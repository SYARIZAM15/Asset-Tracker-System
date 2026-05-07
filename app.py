@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            # --- START AUTO-GENERATE LOGIC ---
            year = "2026"
            prefix = f"JTDI/SDK/{year}/"
            
            # Find the latest sequence number for the current year
            cur.execute("SELECT COUNT(*) FROM assets WHERE tracking_number LIKE %s", (prefix + '%',))
            count = cur.fetchone()[0]
            new_sequence = count + 1
            
            # Formats to 4 digits: JTDI/SDK/2026/0001
            auto_tracking_no = f"{prefix}{new_sequence:04d}"
            # --- END AUTO-GENERATE LOGIC ---

            cur.execute('''INSERT INTO assets (asset_type, tracking_number, cpu_name, serial_number, ram_size, storage_type, status, location) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                        (request.form['asset_type'], auto_tracking_no, request.form['cpu_name'], 
                         request.form['serial_number'], request.form['ram_size'], 
                         request.form['storage_type'], request.form['status'], request.form['location']))
            
            conn.commit()
            return redirect(url_for('index'))
            
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash("Reminder: This Serial Number is already registered in the system.")
            return redirect(url_for('add'))
        finally:
            cur.close()
            conn.close()
            
    return render_template('add.html')
