# Update init_db to include the users table
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Assets table (existing)
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, asset_type TEXT, tracking_number TEXT, cpu_name TEXT, 
        serial_number TEXT UNIQUE, ram_size TEXT, storage_type TEXT, location TEXT, 
        status TEXT, maintenance_logs TEXT
    );''')
    # Users table (New - required for deletion logic to work)
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, full_name TEXT, username TEXT UNIQUE NOT NULL, 
        email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'User'
    );''')
    conn.commit()
    cur.close()
    conn.close()

# Add this route to handle user deletion
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if target user exists and isn't the currently logged-in admin
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    target = cur.fetchone()
    
    if target:
        if target[0] != session.user:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            flash(f"User {target[0]} removed successfully.")
        else:
            flash("You cannot delete your own active admin account.")
    else:
        flash("User not found.")
        
    cur.close()
    conn.close()
    return redirect(url_for('manage_users'))
