import os
import re
import uuid
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify, make_response
from werkzeug.utils import secure_filename
import mysql.connector
import bcrypt
from config import Config, db_connection, init_db
from email_utils import send_otp_email

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Ensure database and tables exist at startup
init_db()


def allowed_file(filename):
    """Check if uploaded file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def login_required(view):
    """Decorator to require user authentication for protected routes."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def role_required(allowed_roles):
    """Decorator to restrict access to specific roles (e.g. ['admin'])."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login', next=request.path))
            current_role = session.get('user_role', 'user')
            if current_role not in allowed_roles:
                flash('Access denied: You do not have permission to view this section.', 'danger')
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


@app.context_processor
def inject_context():
    """Provides user authentication state, live cart counter, and Razorpay key to all templates."""
    customer_id = session.get('user_id')
    cart_count = 0
    profile_image = session.get('user_image')

    if customer_id:
        conn = db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT COALESCE(SUM(ci.quantity), 0) AS total_items
                    FROM cart c
                    JOIN cart_items ci ON c.cart_id = ci.cart_id
                    WHERE c.customer_id = %s
                """, (customer_id,))
                row = cursor.fetchone()
                if row and row['total_items']:
                    cart_count = int(row['total_items'])

                if profile_image is None:
                    cursor.execute("SELECT profile_image FROM customers WHERE customer_id = %s", (customer_id,))
                    cust = cursor.fetchone()
                    if cust and cust.get('profile_image'):
                        profile_image = cust['profile_image']
                        session['user_image'] = profile_image

                cursor.close()
                conn.close()
            except Exception:
                if conn:
                    conn.close()

    return {
        'current_user': {
            'id': session.get('user_id'),
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'role': session.get('user_role'),
            'profile_image': profile_image,
            'is_authenticated': 'user_id' in session
        },
        'cart_count': cart_count,
        'razorpay_key_id': Config.RAZORPAY_KEY_ID
    }


def get_or_create_cart(customer_id):
    """Retrieves or creates a cart record for the given customer."""
    conn = db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT cart_id FROM cart WHERE customer_id = %s", (customer_id,))
        row = cursor.fetchone()
        if row:
            cart_id = row['cart_id']
        else:
            cursor.execute("INSERT INTO cart (customer_id) VALUES (%s)", (customer_id,))
            conn.commit()
            cart_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return cart_id
    except Exception as err:
        print(f"Error in get_or_create_cart: {err}")
        if conn:
            conn.close()
        return None


# -------------------------------------------------------------
# STATIC UPLOADS ROUTE
# -------------------------------------------------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded product photos from the uploads directory."""
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


# -------------------------------------------------------------
# LANDING PAGE / PRODUCT CATALOG
# -------------------------------------------------------------
@app.route('/')
def index():
    """Landing page route displaying categories, search, and catalog products with stock."""
    category_id = request.args.get('category', type=int)
    search_query = request.args.get('search', '').strip()

    conn = db_connection()
    categories = []
    products = []
    selected_category_name = None

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM categories ORDER BY category_name")
            categories = cursor.fetchall()

            sql = """
                SELECT p.*, c.category_name, COALESCE(i.quantity, 0) AS stock_quantity
                FROM products p
                JOIN categories c ON p.category_id = c.category_id
                LEFT JOIN inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1
            """
            params = []
            if category_id:
                sql += " AND p.category_id = %s"
                params.append(category_id)
                for cat in categories:
                    if cat['category_id'] == category_id:
                        selected_category_name = cat['category_name']
                        break

            if search_query:
                sql += " AND (p.product_name LIKE %s OR p.description LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            sql += " ORDER BY p.product_id DESC"
            cursor.execute(sql, tuple(params))
            products = cursor.fetchall()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            print(f"Database fetch error on index: {err}")
            if conn:
                conn.close()

    return render_template(
        'landing/landing.html',
        categories=categories,
        products=products,
        selected_category=category_id,
        selected_category_name=selected_category_name,
        search_query=search_query
    )


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """View single product details page (FLASK 29 & FLASK 32)."""
    conn = db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('index'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, c.category_name, COALESCE(i.quantity, 0) AS stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s AND p.is_active = 1
        """, (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if not product:
            flash('Product not found or currently unavailable.', 'warning')
            return redirect(url_for('index'))

        return render_template('website/product_details.html', product=product)
    except Exception as err:
        print(f"Error loading product details: {err}")
        if conn:
            conn.close()
        flash('Error loading product details.', 'danger')
        return redirect(url_for('index'))


# -------------------------------------------------------------
# AUTHENTICATION: LOGIN, REGISTER, LOGOUT
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Customer and Admin login route."""
    if 'user_id' in session:
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('login/login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Please enter both email and password.', 'danger')
        return render_template('login/login.html', email=email)

    conn = db_connection()
    if not conn:
        flash('Database connection failed. Please try again later.', 'danger')
        return render_template('login/login.html', email=email)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, first_name, last_name, e_mail, password_hash, role, status 
            FROM customers 
            WHERE e_mail = %s
        """, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('login/login.html', email=email)

        if user.get('status') == 'suspended':
            flash('Your account has been suspended. Please contact support.', 'danger')
            return render_template('login/login.html', email=email)

        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            full_name = f"{user['first_name']} {user['last_name']}".strip()
            session['user_id'] = user['customer_id']
            session['user_name'] = full_name
            session['user_email'] = user['e_mail']
            session['user_role'] = user['role']

            flash(f"Welcome, {full_name}!", 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('login/login.html', email=email)

    except mysql.connector.Error as err:
        flash(f"An error occurred during login: {err}", 'danger')
        return render_template('login/login.html', email=email)


# -------------------------------------------------------------
# ADMIN AUTHENTICATION: LOGIN & REGISTER WITH OTP (FLASK 25 & 26)
# -------------------------------------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin dedicated login route (FLASK 26)."""
    if 'user_id' in session and session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'GET':
        return render_template('admin/admin_login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Please provide both admin email and password.', 'danger')
        return render_template('admin/admin_login.html', email=email)

    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return render_template('admin/admin_login.html', email=email)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, first_name, last_name, e_mail, password_hash, role, status 
            FROM customers 
            WHERE e_mail = %s
        """, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or user.get('role') != 'admin':
            flash('Invalid admin credentials or account does not have administrator privileges.', 'danger')
            return render_template('admin/admin_login.html', email=email)

        if user.get('status') == 'suspended':
            flash('Admin account is suspended.', 'danger')
            return render_template('admin/admin_login.html', email=email)

        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            full_name = f"{user['first_name']} {user['last_name']}".strip()
            session['user_id'] = user['customer_id']
            session['user_name'] = full_name
            session['user_email'] = user['e_mail']
            session['user_role'] = 'admin'

            flash(f"Welcome to Admin Dashboard, {full_name}!", 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin email or password.', 'danger')
            return render_template('admin/admin_login.html', email=email)
    except Exception as err:
        flash(f'An error occurred during admin sign in: {err}', 'danger')
        return render_template('admin/admin_login.html', email=email)


@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    """Admin registration with OTP Email Verification (FLASK 25)."""
    if 'user_id' in session and session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'GET':
        return render_template('admin/admin_register.html')

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not full_name or not email or not password or not confirm_password:
        flash('All required fields must be filled.', 'danger')
        return render_template('admin/admin_register.html', full_name=full_name, email=email, phone=phone)

    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, email):
        flash('Please enter a valid email address.', 'danger')
        return render_template('admin/admin_register.html', full_name=full_name, email=email, phone=phone)

    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return render_template('admin/admin_register.html', full_name=full_name, email=email, phone=phone)

    if password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return render_template('admin/admin_register.html', full_name=full_name, email=email, phone=phone)

    conn = db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('admin/admin_register.html', full_name=full_name, email=email, phone=phone)

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT customer_id FROM customers WHERE e_mail = %s", (email,))
    existing = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing:
        flash('An account with this email already exists. Please log in.', 'warning')
        return redirect(url_for('admin_login', email=email))

    otp = str(random.randint(100000, 999999))
    session['admin_reg_data'] = {
        'full_name': full_name,
        'email': email,
        'phone': phone or '0000000000',
        'password': password,
        'otp': otp,
        'expires_at': (datetime.now() + timedelta(minutes=10)).isoformat()
    }

    sent, err_msg = send_otp_email(email, otp, purpose="Admin Registration")
    if not sent:
        print(f"[DEVELOPMENT / SMTP FALLBACK] Admin OTP for {email} is: {otp}")
        flash(f"Notice: Email could not be sent ({err_msg}). For testing, OTP is: {otp}", 'warning')
    else:
        flash('A 6-digit OTP verification code has been sent to your email. Please verify below.', 'info')

    return redirect(url_for('admin_verify_otp'))


@app.route('/admin/verify-otp', methods=['GET', 'POST'])
def admin_verify_otp():
    """Verify Admin registration OTP (FLASK 25)."""
    reg_data = session.get('admin_reg_data')
    if not reg_data:
        flash('Registration session expired or not found. Please register again.', 'warning')
        return redirect(url_for('admin_register'))

    email = reg_data['email']
    parts = email.split('@')
    masked_email = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else email

    if request.method == 'GET':
        return render_template('admin/admin_verify_otp.html', masked_email=masked_email)

    entered_otp = request.form.get('otp', '').strip()
    if not entered_otp:
        flash('Please enter the 6-digit code.', 'danger')
        return render_template('admin/admin_verify_otp.html', masked_email=masked_email)

    expires_at = datetime.fromisoformat(reg_data['expires_at'])
    if datetime.now() > expires_at:
        session.pop('admin_reg_data', None)
        flash('Verification code has expired. Please register again.', 'danger')
        return redirect(url_for('admin_register'))

    if entered_otp != reg_data['otp']:
        flash('Invalid verification code. Please check and try again.', 'danger')
        return render_template('admin/admin_verify_otp.html', masked_email=masked_email)

    # Valid OTP -> Create Admin in Database
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return render_template('admin/admin_verify_otp.html', masked_email=masked_email)

    try:
        name_parts = reg_data['full_name'].split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        hashed_pw = bcrypt.hashpw(reg_data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (first_name, last_name, e_mail, password_hash, role, phone_number)
            VALUES (%s, %s, %s, %s, 'admin', %s)
        """, (first_name, last_name, reg_data['email'], hashed_pw, reg_data['phone']))
        new_admin_id = cursor.lastrowid
        cursor.execute("INSERT IGNORE INTO cart (customer_id) VALUES (%s)", (new_admin_id,))
        conn.commit()
        cursor.close()
        conn.close()

        session.pop('admin_reg_data', None)
        flash('Admin account verified and created successfully! Please sign in below.', 'success')
        return redirect(url_for('admin_login', email=reg_data['email']))
    except Exception as err:
        if conn:
            conn.close()
        flash(f'Error creating admin account: {err}', 'danger')
        return redirect(url_for('admin_register'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Customer registration route."""
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('login/register.html')

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    phone = request.form.get('phone', '').strip()

    if not full_name or not email or not password or not confirm_password:
        flash('All required fields must be filled.', 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)

    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, email):
        flash('Please enter a valid email address.', 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)

    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)

    if password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)

    name_parts = full_name.split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ''

    conn = db_connection()
    if not conn:
        flash('Database connection failed. Please try again later.', 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT customer_id FROM customers WHERE e_mail = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash('An account with this email already exists. Please log in.', 'warning')
            return redirect(url_for('login', email=email))

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        insert_query = """
        INSERT INTO customers (first_name, last_name, e_mail, password_hash, role, phone_number)
        VALUES (%s, %s, %s, %s, 'user', %s)
        """
        cursor.execute(insert_query, (first_name, last_name, email, hashed_pw, phone or '0000000000'))
        new_customer_id = cursor.lastrowid
        # Pre-create empty cart
        cursor.execute("INSERT IGNORE INTO cart (customer_id) VALUES (%s)", (new_customer_id,))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Account created successfully! Please sign in with your credentials.', 'success')
        return redirect(url_for('login'))

    except mysql.connector.Error as err:
        flash(f"Database error during registration: {err}", 'danger')
        return render_template('login/register.html', full_name=full_name, email=email)


@app.route('/logout')
def logout():
    """Log out current user."""
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f"Goodbye {user_name}, you have been logged out.", 'info')
    return redirect(url_for('login'))


# -------------------------------------------------------------
# PASSWORD RESET / OTP ROUTES
# -------------------------------------------------------------
def mask_email(email):
    """Mask email for privacy in UI."""
    if '@' not in email:
        return email
    user, domain = email.split('@', 1)
    if len(user) <= 3:
        masked_user = user[0] + '***'
    else:
        masked_user = user[:2] + '***' + user[-1]
    return f"{masked_user}@{domain}"


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Step 1: Enter registered email to send 6-digit OTP."""
    if request.method == 'GET':
        session.pop('otp_verified', None)
        return render_template('login/forgotpassword.html')

    email = request.form.get('email', '').strip().lower()
    if not email:
        flash('Please enter your registered email address.', 'danger')
        return render_template('login/forgotpassword.html')

    conn = db_connection()
    if not conn:
        flash('Database connection failed. Please try again later.', 'danger')
        return render_template('login/forgotpassword.html', email=email)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT customer_id, first_name, e_mail, status FROM customers WHERE e_mail = %s", (email,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            flash('No account found with this email address.', 'danger')
            return render_template('login/forgotpassword.html', email=email)

        if user.get('status') == 'suspended':
            cursor.close()
            conn.close()
            flash('This account is currently suspended. Please contact support.', 'danger')
            return render_template('login/forgotpassword.html', email=email)

        otp = f"{random.randint(100000, 999999)}"
        expires_at = datetime.now() + timedelta(minutes=10)

        cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
        cursor.execute(
            "INSERT INTO password_resets (email, otp, expires_at) VALUES (%s, %s, %s)",
            (email, otp, expires_at)
        )
        conn.commit()
        cursor.close()
        conn.close()

        sent, err_msg = send_otp_email(email, otp)
        if not sent:
            flash(f"Could not deliver OTP email. Error: {err_msg}", 'danger')
            return render_template('login/forgotpassword.html', email=email)

        session['reset_email'] = email
        session['otp_verified'] = False

        flash(f"A 6-digit verification code has been sent to {email}.", 'success')
        return redirect(url_for('verify_otp'))

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'danger')
        return render_template('login/forgotpassword.html', email=email)


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Step 2: Verify the 6-digit OTP code."""
    email = session.get('reset_email')
    if not email:
        flash('Please request a password reset first.', 'warning')
        return redirect(url_for('forgot_password'))

    if request.method == 'GET':
        return render_template('login/verify_otp.html', masked_email=mask_email(email))

    entered_otp = request.form.get('otp', '').strip()
    if not entered_otp or len(entered_otp) != 6:
        flash('Please enter the full 6-digit code.', 'danger')
        return render_template('login/verify_otp.html', masked_email=mask_email(email))

    conn = db_connection()
    if not conn:
        flash('Database connection failed. Please try again later.', 'danger')
        return render_template('login/verify_otp.html', masked_email=mask_email(email))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM password_resets WHERE email = %s AND otp = %s AND expires_at > NOW() ORDER BY id DESC LIMIT 1",
            (email, entered_otp)
        )
        reset_record = cursor.fetchone()

        if not reset_record:
            cursor.close()
            conn.close()
            flash('Invalid or expired OTP code. Please try again.', 'danger')
            return render_template('login/verify_otp.html', masked_email=mask_email(email))

        cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
        conn.close()

        session['otp_verified'] = True
        flash('OTP verified successfully! Please enter your new password.', 'success')
        return redirect(url_for('updatepassword'))

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'danger')
        return render_template('login/verify_otp.html', masked_email=mask_email(email))


@app.route('/resend-otp')
def resend_otp():
    """Resends a new 6-digit OTP to the email currently in session."""
    email = session.get('reset_email')
    if not email:
        flash('Session expired. Please request a password reset.', 'warning')
        return redirect(url_for('forgot_password'))

    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('verify_otp'))

    try:
        cursor = conn.cursor()
        otp = f"{random.randint(100000, 999999)}"
        expires_at = datetime.now() + timedelta(minutes=10)

        cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
        cursor.execute(
            "INSERT INTO password_resets (email, otp, expires_at) VALUES (%s, %s, %s)",
            (email, otp, expires_at)
        )
        conn.commit()
        cursor.close()
        conn.close()

        sent, err_msg = send_otp_email(email, otp)
        if not sent:
            flash(f"Failed to resend OTP email: {err_msg}", 'danger')
        else:
            flash("A new 6-digit verification code has been sent to your email.", 'info')

        return redirect(url_for('verify_otp'))
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'danger')
        return redirect(url_for('verify_otp'))


@app.route('/updatepassword', methods=['GET', 'POST'])
def updatepassword():
    """Update password route."""
    email = session.get('user_email') or session.get('reset_email')
    is_logged_in = 'user_id' in session
    otp_verified = session.get('otp_verified', False)

    if not email or (not is_logged_in and not otp_verified):
        flash('Unauthorized or session expired. Please verify your email or log in.', 'warning')
        return redirect(url_for('forgot_password'))

    if request.method == 'GET':
        return render_template('login/updatepassword.html')

    new_password = request.form.get('password') or request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not new_password or not confirm_password:
        flash('Please fill in both password fields.', 'danger')
        return render_template('login/updatepassword.html')

    if len(new_password) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return render_template('login/updatepassword.html')

    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return render_template('login/updatepassword.html')

    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return render_template('login/updatepassword.html')

    try:
        cursor = conn.cursor()
        new_hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("UPDATE customers SET password_hash = %s WHERE e_mail = %s", (new_hashed, email))
        conn.commit()
        cursor.close()
        conn.close()

        session.pop('reset_email', None)
        session.pop('otp_verified', None)

        if is_logged_in:
            flash('Your password has been updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Your password has been reset successfully! Please sign in with your new password.', 'success')
            return redirect(url_for('login'))
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'danger')
        return render_template('login/updatepassword.html')


# -------------------------------------------------------------
# USER DASHBOARD
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing user stats."""
    customer_id = session.get('user_id')
    cart_count = 0
    order_count = 0

    conn = db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT COALESCE(SUM(ci.quantity), 0) AS total_items
                FROM cart c
                JOIN cart_items ci ON c.cart_id = ci.cart_id
                WHERE c.customer_id = %s
            """, (customer_id,))
            cart_res = cursor.fetchone()
            if cart_res:
                cart_count = cart_res['total_items']

            cursor.execute("SELECT COUNT(*) AS total_orders FROM orders WHERE customer_id = %s", (customer_id,))
            orders_res = cursor.fetchone()
            if orders_res:
                order_count = orders_res['total_orders']

            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            print(f"Error loading dashboard: {err}")
            if conn:
                conn.close()

    return render_template('website/dashboard.html', cart_count=cart_count, order_count=order_count)


# -------------------------------------------------------------
# USER PROFILE & EDIT PROFILE WITH PHOTO UPLOAD
# -------------------------------------------------------------
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Customer / Admin profile management: update name, phone, and upload profile photo."""
    customer_id = session.get('user_id')
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()

        if not first_name:
            flash('First name is required.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('profile'))

        # Check for profile image upload
        new_image_filename = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"avatar_{uuid.uuid4().hex[:10]}.{ext}"
                file_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
                file.save(file_path)
                new_image_filename = unique_name

        try:
            if new_image_filename:
                cursor.execute("""
                    UPDATE customers 
                    SET first_name = %s, last_name = %s, phone_number = %s, profile_image = %s
                    WHERE customer_id = %s
                """, (first_name, last_name, phone_number, new_image_filename, customer_id))
                session['user_image'] = new_image_filename
            else:
                cursor.execute("""
                    UPDATE customers 
                    SET first_name = %s, last_name = %s, phone_number = %s
                    WHERE customer_id = %s
                """, (first_name, last_name, phone_number, customer_id))

            conn.commit()
            full_name = f"{first_name} {last_name}".strip()
            session['user_name'] = full_name
            flash('Profile updated successfully!', 'success')
        except Exception as err:
            flash(f'Error updating profile: {err}', 'danger')

    cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('website/profile.html', user=user)


# -------------------------------------------------------------
# ADMIN MANAGEMENT ROUTES
# -------------------------------------------------------------
@app.route('/admin')
@role_required(['admin'])
def admin_dashboard():
    """Admin dashboard with overview counts."""
    total_products = 0
    total_categories = 0
    total_orders = 0
    total_users = 0

    conn = db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS count FROM products")
            total_products = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) AS count FROM categories")
            total_categories = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) AS count FROM orders")
            total_orders = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) AS count FROM customers WHERE role != 'admin'")
            total_users = cursor.fetchone()['count']

            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Admin dashboard error: {err}")
            if conn:
                conn.close()

    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        total_categories=total_categories,
        total_orders=total_orders,
        total_users=total_users
    )


@app.route('/admin/products')
@role_required(['admin'])
def admin_products():
    """Admin view: List all products with search, category and price filters (FLASK 31)."""
    search_query = request.args.get('search', '').strip()
    category_id = request.args.get('category', type=int)
    max_price = request.args.get('max_price', type=float)

    conn = db_connection()
    products = []
    categories = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Fetch categories for filter dropdown
            cursor.execute("SELECT * FROM categories ORDER BY category_name")
            categories = cursor.fetchall()

            sql = """
                SELECT p.*, c.category_name, COALESCE(i.quantity, 0) AS stock_quantity
                FROM products p
                JOIN categories c ON p.category_id = c.category_id
                LEFT JOIN inventory i ON p.product_id = i.product_id
                WHERE 1=1
            """
            params = []
            if search_query:
                sql += " AND (p.product_name LIKE %s OR p.description LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])
            if category_id:
                sql += " AND p.category_id = %s"
                params.append(category_id)
            if max_price is not None and max_price > 0:
                sql += " AND p.price <= %s"
                params.append(max_price)

            sql += " ORDER BY p.product_id DESC"
            cursor.execute(sql, tuple(params))
            products = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Admin products error: {err}")
            if conn:
                conn.close()

    return render_template(
        'admin/products.html',
        products=products,
        categories=categories,
        search_query=search_query,
        selected_category=category_id,
        max_price=max_price
    )


@app.route('/admin/product/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_product_add():
    """Admin feature: Add product with photo upload."""
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin_products'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/product_form.html', is_edit=False, product=None, categories=categories)

    # Handle POST
    product_name = request.form.get('product_name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    stock_quantity = request.form.get('stock_quantity', default=10, type=int)
    description = request.form.get('description', '').strip()

    if not product_name or not category_id or price is None:
        flash('Product name, category, and price are required.', 'danger')
        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/product_form.html', is_edit=False, product=None, categories=categories)

    # Handle photo upload
    image_filename = None
    if 'product_image' in request.files:
        file = request.files['product_image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex[:12]}.{ext}"
            file_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
            file.save(file_path)
            image_filename = unique_name

    try:
        cursor.execute("""
            INSERT INTO products (category_id, product_name, description, price, image_url, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (category_id, product_name, description, price, image_filename))
        product_id = cursor.lastrowid

        # Insert inventory
        cursor.execute("""
            INSERT INTO inventory (product_id, quantity)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE quantity = VALUES(quantity)
        """, (product_id, stock_quantity))

        conn.commit()
        cursor.close()
        conn.close()
        flash(f'Product "{product_name}" uploaded and added successfully!', 'success')
        return redirect(url_for('admin_products'))

    except mysql.connector.Error as err:
        flash(f'Error adding product: {err}', 'danger')
        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/product_form.html', is_edit=False, product=None, categories=categories)


@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_product_edit(product_id):
    """Admin feature: Edit product details and optionally change photo."""
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin_products'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("""
            SELECT p.*, COALESCE(i.quantity, 0) AS stock_quantity
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()

        if not product:
            cursor.close()
            conn.close()
            flash('Product not found.', 'danger')
            return redirect(url_for('admin_products'))

        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/product_form.html', is_edit=True, product=product, categories=categories)

    # Handle POST update
    product_name = request.form.get('product_name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    stock_quantity = request.form.get('stock_quantity', default=0, type=int)
    description = request.form.get('description', '').strip()
    is_active = 1 if request.form.get('is_active') == '1' else 0

    # Check if new photo was uploaded
    new_image_filename = None
    if 'product_image' in request.files:
        file = request.files['product_image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex[:12]}.{ext}"
            file_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
            file.save(file_path)
            new_image_filename = unique_name

    try:
        if new_image_filename:
            cursor.execute("""
                UPDATE products 
                SET product_name = %s, category_id = %s, price = %s, description = %s, image_url = %s, is_active = %s
                WHERE product_id = %s
            """, (product_name, category_id, price, description, new_image_filename, is_active, product_id))
        else:
            cursor.execute("""
                UPDATE products 
                SET product_name = %s, category_id = %s, price = %s, description = %s, is_active = %s
                WHERE product_id = %s
            """, (product_name, category_id, price, description, is_active, product_id))

        # Update inventory
        cursor.execute("""
            INSERT INTO inventory (product_id, quantity)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE quantity = VALUES(quantity)
        """, (product_id, stock_quantity))

        conn.commit()
        cursor.close()
        conn.close()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin_products'))

    except mysql.connector.Error as err:
        flash(f'Error updating product: {err}', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('admin_product_edit', product_id=product_id))


@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@role_required(['admin'])
def admin_product_delete(product_id):
    """Admin feature: Delete/deactivate product."""
    conn = db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE products SET is_active = 0 WHERE product_id = %s", (product_id,))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Product removed from active catalog.', 'info')
        except Exception as err:
            flash(f'Error removing product: {err}', 'danger')
            if conn:
                conn.close()
    return redirect(url_for('admin_products'))


@app.route('/admin/categories', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_categories():
    """Admin feature: Manage and add categories."""
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        category_name = request.form.get('category_name', '').strip()
        if category_name:
            try:
                cursor.execute("INSERT INTO categories (category_name) VALUES (%s)", (category_name,))
                conn.commit()
                flash(f'Category "{category_name}" added successfully!', 'success')
            except mysql.connector.Error as err:
                flash(f'Error adding category: {err}', 'danger')

    cursor.execute("""
        SELECT c.*, COUNT(p.product_id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.category_id = p.category_id
        GROUP BY c.category_id
        ORDER BY c.category_name
    """)
    categories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/category/delete/<int:category_id>', methods=['POST'])
@role_required(['admin'])
def admin_category_delete(category_id):
    """Admin feature: Delete category if empty."""
    conn = db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS count FROM products WHERE category_id = %s", (category_id,))
            res = cursor.fetchone()
            if res and res['count'] > 0:
                flash('Cannot delete category: products are assigned to it.', 'warning')
            else:
                cursor.execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
                conn.commit()
                flash('Category deleted successfully.', 'info')
            cursor.close()
            conn.close()
        except Exception as err:
            flash(f'Error deleting category: {err}', 'danger')
            if conn:
                conn.close()
    return redirect(url_for('admin_categories'))


@app.route('/admin/orders')
@role_required(['admin'])
def admin_orders():
    """Admin feature: View customer orders."""
    conn = db_connection()
    orders = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.*, c.first_name, c.last_name, c.e_mail, c.phone_number,
                       p.payment_status, p.payment_method, p.transaction_id
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                LEFT JOIN payments p ON o.order_id = p.order_id
                ORDER BY o.order_id DESC
            """)
            orders = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Error fetching admin orders: {err}")
            if conn:
                conn.close()

    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@role_required(['admin'])
def admin_order_status(order_id):
    """Admin feature: Update order status."""
    new_status = request.form.get('status', '').strip()
    if new_status in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
        conn = db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET order_status = %s WHERE order_id = %s", (new_status, order_id))
                conn.commit()
                cursor.close()
                conn.close()
                flash(f'Order #{order_id} status updated to {new_status}.', 'success')
            except Exception as err:
                flash(f'Error updating order status: {err}', 'danger')
                if conn:
                    conn.close()
    return redirect(url_for('admin_orders'))


# -------------------------------------------------------------
# ADMIN PROFILE & PROFILE PHOTO UPDATE (DAY 8 SYLLABUS)
# -------------------------------------------------------------
@app.route('/admin/profile', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_profile():
    """Admin Profile management: view info, update name, email, change password, and replace avatar (FLASK 31 / Day 8)."""
    admin_id = session.get('user_id')
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip()
        new_password = request.form.get('password', '').strip()

        if not first_name or not email:
            flash('First name and email address are required.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_profile'))

        # Fetch current admin data for old photo reference
        cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (admin_id,))
        current_admin = cursor.fetchone()
        old_image_name = current_admin.get('profile_image') if current_admin else None

        # Optional profile photo upload & replace
        new_image_filename = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                new_image_filename = f"admin_avatar_{uuid.uuid4().hex[:10]}.{ext}"
                file_path = os.path.join(Config.UPLOAD_FOLDER, new_image_filename)
                file.save(file_path)

                # Delete old photo file if it existed
                if old_image_name:
                    old_path = os.path.join(Config.UPLOAD_FOLDER, old_image_name)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass

        try:
            update_fields = ["first_name = %s", "last_name = %s", "e_mail = %s", "phone_number = %s"]
            update_params = [first_name, last_name, email, phone_number]

            if new_password:
                if len(new_password) < 6:
                    flash('New password must be at least 6 characters long.', 'warning')
                else:
                    hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    update_fields.append("password_hash = %s")
                    update_params.append(hashed_pw)

            if new_image_filename:
                update_fields.append("profile_image = %s")
                update_params.append(new_image_filename)
                session['user_image'] = new_image_filename

            update_params.append(admin_id)
            sql_update = f"UPDATE customers SET {', '.join(update_fields)} WHERE customer_id = %s"
            cursor.execute(sql_update, tuple(update_params))
            conn.commit()

            full_name = f"{first_name} {last_name}".strip()
            session['user_name'] = full_name
            session['user_email'] = email

            flash('Admin profile updated successfully!', 'success')
        except Exception as err:
            flash(f'Error updating admin profile: {err}', 'danger')

    cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (admin_id,))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('admin/admin_profile.html', admin=admin)


# -------------------------------------------------------------
# ADMIN SINGLE PRODUCT DETAILS (DAY 5 SYLLABUS)
# -------------------------------------------------------------
@app.route('/admin/product/view/<int:product_id>')
@app.route('/admin/view-item/<int:product_id>')
@role_required(['admin'])
def admin_product_view(product_id):
    """Single product detailed inspection view for admin (Day 5 syllabus)."""
    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin_products'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, c.category_name, COALESCE(i.quantity, 0) AS stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if not product:
            flash('Product not found.', 'danger')
            return redirect(url_for('admin_products'))

        return render_template('admin/view_item.html', product=product)
    except Exception as err:
        flash(f'Error loading product: {err}', 'danger')
        if conn:
            conn.close()
        return redirect(url_for('admin_products'))


# -------------------------------------------------------------
# SHOPPING CART FUNCTIONALITY
# -------------------------------------------------------------
@app.route('/cart')
@login_required
def cart_view():
    """View items in the customer's cart."""
    customer_id = session.get('user_id')
    cart_id = get_or_create_cart(customer_id)

    items = []
    total_amount = 0.0

    conn = db_connection()
    if conn and cart_id:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ci.cart_item_id, ci.product_id, ci.quantity,
                       p.product_name, p.price, p.image_url,
                       (ci.quantity * p.price) AS subtotal
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.product_id
                WHERE ci.cart_id = %s
                ORDER BY ci.cart_item_id ASC
            """, (cart_id,))
            items = cursor.fetchall()

            for item in items:
                total_amount += float(item['subtotal'])

            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Error viewing cart: {err}")
            if conn:
                conn.close()

    return render_template('website/cart.html', items=items, total_amount=total_amount)


@app.route('/cart/add/<int:product_id>', methods=['POST', 'GET'])
@login_required
def cart_add(product_id):
    """Add a product to the user's shopping cart."""
    customer_id = session.get('user_id')
    cart_id = get_or_create_cart(customer_id)
    quantity = request.form.get('quantity', default=1, type=int)
    if quantity < 1:
        quantity = 1

    conn = db_connection()
    if not conn or not cart_id:
        flash('Failed to connect to cart.', 'danger')
        return redirect(url_for('index'))

    try:
        cursor = conn.cursor(dictionary=True)
        # Check product stock
        cursor.execute("""
            SELECT p.product_name, COALESCE(i.quantity, 0) AS stock_quantity
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        prod = cursor.fetchone()

        if not prod:
            cursor.close()
            conn.close()
            flash('Product not found.', 'danger')
            return redirect(url_for('index'))

        if prod['stock_quantity'] < quantity:
            cursor.close()
            conn.close()
            flash(f'Sorry, only {prod["stock_quantity"]} units in stock.', 'warning')
            return redirect(url_for('index'))

        # Add or update cart_items
        cursor.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
        """, (cart_id, product_id, quantity))

        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Added {quantity} x "{prod["product_name"]}" to your cart.', 'success')
    except Exception as err:
        flash(f'Error adding to cart: {err}', 'danger')
        if conn:
            conn.close()

    return redirect(url_for('cart_view'))


# -------------------------------------------------------------
# AJAX ADD TO CART (DAY 11 AMAZON-STYLE WITHOUT PAGE RELOAD)
# -------------------------------------------------------------
@app.route('/cart/add-ajax/<int:product_id>', methods=['GET', 'POST'])
@app.route('/user/add-to-cart-ajax/<int:product_id>', methods=['GET', 'POST'])
def cart_add_ajax(product_id):
    """AJAX endpoint for instant Add-To-Cart without page reload (Day 11 syllabus)."""
    customer_id = session.get('user_id')
    if not customer_id:
        return jsonify({
            'success': False,
            'message': 'Please log in to add items to your cart.',
            'login_required': True
        }), 401

    quantity = request.form.get('quantity', type=int) or request.args.get('quantity', default=1, type=int)
    if quantity < 1:
        quantity = 1

    cart_id = get_or_create_cart(customer_id)
    conn = db_connection()
    if not conn or not cart_id:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.product_name, p.price, COALESCE(i.quantity, 0) AS stock_quantity
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s AND p.is_active = 1
        """, (product_id,))
        prod = cursor.fetchone()

        if not prod:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Product not available.'}), 404

        if prod['stock_quantity'] < quantity:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': f"Sorry, only {prod['stock_quantity']} units in stock."
            }), 400

        cursor.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
        """, (cart_id, product_id, quantity))
        conn.commit()

        # Recalculate total items in cart for instant badge update
        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) AS total_count
            FROM cart_items
            WHERE cart_id = %s
        """, (cart_id,))
        res = cursor.fetchone()
        total_count = int(res['total_count']) if res else 0

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f"Added '{prod['product_name']}' to cart!",
            'cart_count': total_count,
            'product_name': prod['product_name']
        })
    except Exception as err:
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': str(err)}), 500


@app.route('/cart/update', methods=['POST'])
@login_required
def cart_update():
    """Adjust quantity of a cart item (+ or -)."""
    cart_item_id = request.form.get('cart_item_id', type=int)
    action = request.form.get('action', '')

    conn = db_connection()
    if conn and cart_item_id:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT quantity FROM cart_items WHERE cart_item_id = %s", (cart_item_id,))
            item = cursor.fetchone()
            if item:
                current_qty = item['quantity']
                if action == 'increase':
                    new_qty = current_qty + 1
                    cursor.execute("UPDATE cart_items SET quantity = %s WHERE cart_item_id = %s", (new_qty, cart_item_id))
                elif action == 'decrease':
                    new_qty = current_qty - 1
                    if new_qty <= 0:
                        cursor.execute("DELETE FROM cart_items WHERE cart_item_id = %s", (cart_item_id,))
                    else:
                        cursor.execute("UPDATE cart_items SET quantity = %s WHERE cart_item_id = %s", (new_qty, cart_item_id))
                conn.commit()
            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Error updating cart item: {err}")
            if conn:
                conn.close()

    return redirect(url_for('cart_view'))


@app.route('/cart/remove/<int:cart_item_id>', methods=['POST', 'GET'])
@login_required
def cart_remove(cart_item_id):
    """Remove a single line item from the cart."""
    conn = db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart_items WHERE cart_item_id = %s", (cart_item_id,))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Item removed from cart.', 'info')
        except Exception as err:
            flash(f'Error removing item: {err}', 'danger')
            if conn:
                conn.close()
    return redirect(url_for('cart_view'))


@app.route('/cart/clear', methods=['POST', 'GET'])
@login_required
def cart_clear():
    """Empty all items from customer's cart."""
    customer_id = session.get('user_id')
    cart_id = get_or_create_cart(customer_id)
    conn = db_connection()
    if conn and cart_id:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Shopping cart cleared.', 'info')
        except Exception as err:
            flash(f'Error clearing cart: {err}', 'danger')
            if conn:
                conn.close()
    return redirect(url_for('cart_view'))


# -------------------------------------------------------------
# CHECKOUT & RAZORPAY PAYMENT
# -------------------------------------------------------------
@app.route('/checkout')
@login_required
def checkout():
    """Checkout page showing delivery address form and Razorpay payment."""
    customer_id = session.get('user_id')
    cart_id = get_or_create_cart(customer_id)

    conn = db_connection()
    if not conn:
        flash('Database error.', 'danger')
        return redirect(url_for('cart_view'))

    try:
        cursor = conn.cursor(dictionary=True)
        # Fetch cart items
        cursor.execute("""
            SELECT ci.cart_item_id, ci.quantity, p.product_name, p.price,
                   (ci.quantity * p.price) AS subtotal
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.product_id
            WHERE ci.cart_id = %s
        """, (cart_id,))
        items = cursor.fetchall()

        if not items:
            cursor.close()
            conn.close()
            flash('Your cart is empty. Add products before checking out.', 'warning')
            return redirect(url_for('index'))

        total_amount = sum(float(it['subtotal']) for it in items)

        # Fetch customer info & existing default address
        cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
        customer = cursor.fetchone()

        cursor.execute("""
            SELECT * FROM address 
            WHERE customer_id = %s 
            ORDER BY is_default DESC, address_id DESC LIMIT 1
        """, (customer_id,))
        default_address = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template(
            'website/checkout.html',
            items=items,
            total_amount=total_amount,
            customer=customer,
            default_address=default_address
        )
    except Exception as err:
        flash(f'Checkout error: {err}', 'danger')
        if conn:
            conn.close()
        return redirect(url_for('cart_view'))


@app.route('/payment/process', methods=['POST'])
@login_required
def payment_process():
    """Process payment response, create order, deduct stock, and empty cart."""
    customer_id = session.get('user_id')
    cart_id = get_or_create_cart(customer_id)

    phone_number = request.form.get('phone_number', '').strip()
    address_line = request.form.get('address_line', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    pincode = request.form.get('pincode', '').strip()
    razorpay_payment_id = request.form.get('razorpay_payment_id', '').strip()

    if not address_line or not city or not state or not pincode:
        flash('All address fields are required for delivery.', 'danger')
        return redirect(url_for('checkout'))

    conn = db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('checkout'))

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch current cart items
        cursor.execute("""
            SELECT ci.product_id, ci.quantity, p.price, p.product_name
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.product_id
            WHERE ci.cart_id = %s
        """, (cart_id,))
        cart_items = cursor.fetchall()

        if not cart_items:
            cursor.close()
            conn.close()
            flash('Your cart is empty.', 'warning')
            return redirect(url_for('index'))

        total_amount = sum(float(item['price']) * item['quantity'] for item in cart_items)

        # 2. Save shipping address
        cursor.execute("""
            INSERT INTO address (customer_id, address_line, city, state, pincode, country, is_default)
            VALUES (%s, %s, %s, %s, %s, 'INDIA', 1)
        """, (customer_id, address_line, city, state, pincode))
        address_id = cursor.lastrowid

        # Update phone number on customer record if missing
        if phone_number:
            cursor.execute("UPDATE customers SET phone_number = %s WHERE customer_id = %s AND (phone_number = '' OR phone_number = '0000000000')", (phone_number, customer_id))

        # 3. Create order
        timestamp_str = datetime.now().strftime('%Y%m%d%H%M%S')
        order_number = f"ORD-{timestamp_str}-{random.randint(100, 999)}"

        cursor.execute("""
            INSERT INTO orders (order_number, customer_id, address_id, order_status, total_amount)
            VALUES (%s, %s, %s, 'processing', %s)
        """, (order_number, customer_id, address_id, total_amount))
        order_id = cursor.lastrowid

        # 4. Insert order items & reduce inventory
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['product_id'], item['quantity'], item['price']))

            cursor.execute("""
                UPDATE inventory 
                SET quantity = GREATEST(0, quantity - %s)
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        # 5. Insert payment record
        base_txn_id = razorpay_payment_id or f"pay_rzp_{uuid.uuid4().hex[:10]}"
        cursor.execute("SELECT payment_id FROM payments WHERE transaction_id = %s", (base_txn_id,))
        if cursor.fetchone():
            txn_id = f"{base_txn_id}_{uuid.uuid4().hex[:6]}"
        else:
            txn_id = base_txn_id

        cursor.execute("""
            INSERT INTO payments (order_id, payment_method, payment_status, amount_paid, transaction_id)
            VALUES (%s, 'Razorpay', 'completed', %s, %s)
        """, (order_id, total_amount, txn_id))

        # 6. Insert shipment tracking record
        tracking_num = f"TRK-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute("""
            INSERT INTO shipments (order_id, address_id, phone_number, tracking_number, shipment_status)
            VALUES (%s, %s, %s, %s, 'Order Confirmed')
        """, (order_id, address_id, phone_number, tracking_num))

        # 7. Clear cart items
        cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Payment verified successfully! Your order has been placed.', 'success')
        return redirect(url_for('order_success', order_id=order_id))

    except Exception as err:
        flash(f'Payment processing error: {err}', 'danger')
        if conn:
            conn.close()
        return redirect(url_for('checkout'))


# -------------------------------------------------------------
# ORDER CONFIRMATION, INVOICE DOWNLOAD & HISTORY
# -------------------------------------------------------------
@app.route('/order/<int:order_id>/success')
@login_required
def order_success(order_id):
    """Order confirmation view with direct invoice download link."""
    customer_id = session.get('user_id')
    user_role = session.get('user_role')

    conn = db_connection()
    if not conn:
        flash('Database error.', 'danger')
        return redirect(url_for('index'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order or (order['customer_id'] != customer_id and user_role != 'admin'):
            cursor.close()
            conn.close()
            flash('Order not found or access denied.', 'danger')
            return redirect(url_for('index'))

        cursor.execute("SELECT * FROM address WHERE address_id = %s", (order['address_id'],))
        address = cursor.fetchone()

        cursor.execute("SELECT * FROM payments WHERE order_id = %s LIMIT 1", (order_id,))
        payment = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template('website/order_success.html', order=order, address=address, payment=payment)
    except Exception as err:
        flash(f'Error loading order confirmation: {err}', 'danger')
        if conn:
            conn.close()
        return redirect(url_for('index'))


@app.route('/order/<int:order_id>/invoice')
@login_required
def order_invoice(order_id):
    """Render printable / downloadable tax invoice."""
    customer_id = session.get('user_id')
    user_role = session.get('user_role')

    conn = db_connection()
    if not conn:
        flash('Database error.', 'danger')
        return redirect(url_for('index'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order or (order['customer_id'] != customer_id and user_role != 'admin'):
            cursor.close()
            conn.close()
            flash('Invoice not found or unauthorized access.', 'danger')
            return redirect(url_for('index'))

        cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (order['customer_id'],))
        customer = cursor.fetchone()

        cursor.execute("SELECT * FROM address WHERE address_id = %s", (order['address_id'],))
        address = cursor.fetchone()

        cursor.execute("SELECT * FROM payments WHERE order_id = %s LIMIT 1", (order_id,))
        payment = cursor.fetchone()

        cursor.execute("""
            SELECT oi.*, p.product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        items = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template(
            'website/invoice.html',
            order=order,
            customer=customer,
            address=address,
            payment=payment,
            items=items
        )
    except Exception as err:
        flash(f'Error loading invoice: {err}', 'danger')
        if conn:
            conn.close()
        return redirect(url_for('index'))


@app.route('/orders')
@login_required
def customer_orders():
    """Customer view of their order history."""
    customer_id = session.get('user_id')

    conn = db_connection()
    orders = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.*, p.payment_status, p.transaction_id
                FROM orders o
                LEFT JOIN payments p ON o.order_id = p.order_id
                WHERE o.customer_id = %s
                ORDER BY o.order_id DESC
            """, (customer_id,))
            orders = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as err:
            print(f"Error fetching customer orders: {err}")
            if conn:
                conn.close()

    return render_template('website/orders.html', orders=orders)


# -------------------------------------------------------------
# DOWNLOAD INVOICE PDF ROUTE (DAY 14 SYLLABUS - xhtml2pdf)
# -------------------------------------------------------------
@app.route('/user/download-invoice/<int:order_id>')
@app.route('/order/<int:order_id>/download-invoice')
@login_required
def download_invoice(order_id):
    """Generates and serves downloadable PDF invoice using xhtml2pdf (Day 14 syllabus)."""
    customer_id = session.get('user_id')
    user_role = session.get('user_role')

    conn = db_connection()
    if not conn:
        flash('Database error.', 'danger')
        return redirect(url_for('customer_orders'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order or (order['customer_id'] != customer_id and user_role != 'admin'):
            cursor.close()
            conn.close()
            flash('Order not found or unauthorized access.', 'danger')
            return redirect(url_for('customer_orders'))

        cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (order['customer_id'],))
        customer = cursor.fetchone()

        cursor.execute("SELECT * FROM address WHERE address_id = %s", (order['address_id'],))
        address = cursor.fetchone()

        cursor.execute("SELECT * FROM payments WHERE order_id = %s LIMIT 1", (order_id,))
        payment = cursor.fetchone()

        cursor.execute("""
            SELECT oi.*, p.product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        items = cursor.fetchall()
        cursor.close()
        conn.close()

        # Render HTML invoice template
        html = render_template(
            'website/invoice.html',
            order=order,
            customer=customer,
            address=address,
            payment=payment,
            items=items,
            is_pdf=True
        )

        # Convert HTML to PDF using utils.pdf_generator
        from utils.pdf_generator import generate_pdf
        pdf_buffer = generate_pdf(html)

        if not pdf_buffer:
            # Fallback to browser view
            flash('Notice: Opened printable invoice. Use Print / Save as PDF.', 'info')
            return redirect(url_for('order_invoice', order_id=order_id))

        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=invoice_{order_id}.pdf"
        return response

    except Exception as err:
        print(f"Error generating PDF invoice: {err}")
        if conn:
            conn.close()
        flash('Notice: Opening printable invoice view.', 'info')
        return redirect(url_for('order_invoice', order_id=order_id))


# -------------------------------------------------------------
# CURRICULUM SYLLABUS ROUTE ALIASES (DAY 1 TO DAY 14 COMPATIBILITY)
# -------------------------------------------------------------
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup_alias():
    return admin_register()


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login_alias():
    return admin_login()


@app.route('/admin-dashboard')
def admin_dashboard_alias():
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-logout')
def admin_logout_alias():
    return redirect(url_for('logout'))


@app.route('/admin/add-item', methods=['GET', 'POST'])
def admin_add_item_alias():
    return admin_product_add()


@app.route('/admin/item-list')
def admin_item_list_alias():
    return admin_products()


@app.route('/admin/update-item/<int:product_id>', methods=['GET', 'POST'])
def admin_update_item_alias(product_id):
    return admin_product_edit(product_id)


@app.route('/admin/delete-item/<int:product_id>', methods=['GET', 'POST'])
def admin_delete_item_alias(product_id):
    return admin_product_delete(product_id)


@app.route('/user-register', methods=['GET', 'POST'])
def user_register_alias():
    return register()


@app.route('/user-login', methods=['GET', 'POST'])
def user_login_alias():
    return login()


@app.route('/user-dashboard')
def user_dashboard_alias():
    return redirect(url_for('dashboard'))


@app.route('/user-logout')
def user_logout_alias():
    return redirect(url_for('logout'))


@app.route('/user/products')
def user_products_alias():
    return index()


@app.route('/user/product/<int:product_id>')
def user_product_alias(product_id):
    return product_detail(product_id)


@app.route('/user/cart')
def user_cart_alias():
    return redirect(url_for('cart_view'))


@app.route('/user/add-to-cart/<int:product_id>', methods=['GET', 'POST'])
def user_add_to_cart_alias(product_id):
    return cart_add(product_id)


@app.route('/user/cart/increase/<int:cart_item_id>')
def user_cart_increase_alias(cart_item_id):
    conn = db_connection()
    if conn and cart_item_id:
        cursor = conn.cursor()
        cursor.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE cart_item_id = %s", (cart_item_id,))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('cart_view'))


@app.route('/user/cart/decrease/<int:cart_item_id>')
def user_cart_decrease_alias(cart_item_id):
    conn = db_connection()
    if conn and cart_item_id:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT quantity FROM cart_items WHERE cart_item_id = %s", (cart_item_id,))
        item = cursor.fetchone()
        if item:
            if item['quantity'] <= 1:
                cursor.execute("DELETE FROM cart_items WHERE cart_item_id = %s", (cart_item_id,))
            else:
                cursor.execute("UPDATE cart_items SET quantity = quantity - 1 WHERE cart_item_id = %s", (cart_item_id,))
            conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('cart_view'))


@app.route('/user/cart/remove/<int:cart_item_id>')
def user_cart_remove_alias(cart_item_id):
    return cart_remove(cart_item_id)


@app.route('/user/my-orders')
def user_my_orders_alias():
    return redirect(url_for('customer_orders'))


@app.route('/user/order-success/<int:order_id>')
def user_order_success_alias(order_id):
    return redirect(url_for('order_success', order_id=order_id))


if __name__ == '__main__':
    app.run(debug=True)
