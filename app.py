import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration ---
# Fix database URL format for SQLAlchemy if provided as postgres:// by Render
db_url = os.environ.get('DATABASE_URL', 'sqlite:///complaints.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')

# Flask-Mail Config
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)

# Import models after db initialization to avoid circular imports
from models import User, Complaint

@app.before_first_request
def create_tables():
    db.create_all()

# --- Routes ---

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()  # Force lowercase for mobile inputs
        matric_no = request.form.get('matric_no', '').strip()
        department = request.form.get('department', '').strip()
        password = request.form.get('password')

        # --- Email & Student Validation Rule ---
        # Checks if email ends with @bouesti.edu.ng or any subdomain like .bouesti.edu.ng
        is_valid_school_email = email.endswith('bouesti.edu.ng')
        
        if not is_valid_school_email:
            flash('You cannot create an account because you are not recognized as a BOUESTI science student. Please use your official school email.', 'danger')
            return redirect(url_for('register'))

        # Check if user or matric number already exists
        existing_user = User.query.filter((User.email == email) | (User.matric_no == matric_no)).first()
        if existing_user:
            flash('Email or Matriculation Number already registered.', 'warning')
            return redirect(url_for('register'))

        # Create new student account
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(
            full_name=full_name,
            email=email,
            matric_no=matric_no,
            department=department,
            password=hashed_password,
            is_admin=False
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['full_name'] = user.full_name
            session['is_admin'] = user.is_admin

            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Additional application routes (student_dashboard, submit_complaint, admin_dashboard, etc.) continue below...

if __name__ == '__main__':
    app.run(debug=True)