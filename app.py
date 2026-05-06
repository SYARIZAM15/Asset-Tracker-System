@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''INSERT INTO assets (asset_type, cpu_name, serial_number, ram_size, storage_type, status, location) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                        (request.form['asset_type'], request.form['cpu_name'], request.form['serial_number'], 
                         request.form['ram_size'], request.form['storage_type'], request.form['status'], request.form['location']))
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

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM assets WHERE id = %s', (id,))
    asset = cur.fetchone()

    if request.method == 'POST':
        try:
            log_entry = f"{request.form['category']}: {request.form['action']}"
            new_logs = (asset['maintenance_logs'] + "\n" + log_entry) if asset['maintenance_logs'] else log_entry
            
            cur.execute('''UPDATE assets SET asset_type=%s, cpu_name=%s, ram_size=%s, storage_type=%s, location=%s, status=%s, maintenance_logs=%s 
                        WHERE id=%s''',
                        (request.form['asset_type'], request.form['cpu_name'], request.form['ram_size'], 
                         request.form['storage_type'], request.form['location'], request.form['status'], new_logs, id))
            conn.commit()
            return redirect(url_for('index'))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash("Update Failed: That Serial Number is already assigned to another asset.")
            return redirect(url_for('edit', id=id))
    
    cur.close()
    conn.close()
    return render_template('edit.html', asset=asset)
