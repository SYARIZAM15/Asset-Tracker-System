import os, io, qrcode, base64, psycopg2, psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'jtdi_secure_master_2026'
app.permanent_session_lifetime = timedelta(hours=8)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# --- USER MANAGEMENT ROUTES ---

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'Admin': 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        pw = generate_password_hash(request.form.get('password'))
        try:
            cur.execute("INSERT INTO users (full_name, username, email, password, role) VALUES (%s,%s,%s,%s,%s)", 
                        (request.form.get('full_name'), request.form.get('username'), 
                         request.form.get('email').strip().lower(), pw, request.form.get('role')))
            conn.commit()
            flash("Staff member added successfully!")
        except Exception as e:
            conn.rollback()
            flash("Error: Username or Email already exists.")

    # Fetch all users for the list
    cur.execute("SELECT id, full_name, username, email, role FROM users ORDER BY id ASC")
    users = cur.fetchall()
    
    cur.close(); conn.close()
    return render_template('manage_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection(); cur = conn.cursor()
    # Prevent user from deleting their own active account
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    target = cur.fetchone()
    
    if target and target[0] != session.user:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash("User removed.")
    else:
        flash("You cannot delete your own account.")
        
    cur.close(); conn.close()
    return redirect(url_for('manage_users'))

# --- (KEEP ALL OTHER ROUTES: /, /login, /add, /edit, /view, /qr, /logout) ---
