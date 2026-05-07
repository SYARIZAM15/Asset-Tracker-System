@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Get parameters from the URL
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Base SQL Query
    query = "SELECT * FROM assets WHERE 1=1"
    params = []

    # Apply Search (S/N, Tracking No, or Brand)
    if search_query:
        query += " AND (serial_number ILIKE %s OR tracking_number ILIKE %s OR cpu_name ILIKE %s)"
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
    
    # Apply Category Filter
    if category_filter:
        query += " AND asset_type = %s"
        params.append(category_filter)

    query += " ORDER BY id DESC"
    cur.execute(query, tuple(params))
    data = cur.fetchall()

    # Calculate Counts based on the current filtered results
    stats = {
        'total': len(data),
        'working': len([r for r in data if r['status'] == 'Working']),
        'maint': len([r for r in data if r['status'] == 'Maintenance']),
        'faulty': len([r for r in data if r['status'] == 'Faulty'])
    }
    
    cur.close()
    conn.close()
    
    return render_template('assets.html', 
                           data=data, 
                           **stats, 
                           s_query=search_query, 
                           c_filter=category_filter)
