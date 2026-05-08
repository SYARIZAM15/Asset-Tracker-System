@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if the user exists and isn't the current logged-in admin
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    target_user = cur.fetchone()
    
    if target_user:
        if target_user[0] != session.user:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            flash(f"User '{target_user[0]}' has been removed.")
        else:
            flash("Error: You cannot delete your own admin account while logged in.")
    else:
        flash("Error: User not found.")
        
    cur.close()
    conn.close()
    # Ensure this redirects back to the management page
    return redirect(url_for('manage_users'))
