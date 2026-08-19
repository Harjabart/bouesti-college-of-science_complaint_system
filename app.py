import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================================================
# 1. APPLICATION & DATABASE CONFIGURATION
# =========================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bouesti-secret-key-2026-production')

# Fix PostgreSQL URI scheme for SQLAlchemy 2.0+ on Render
db_uri = os.environ.get("DATABASE_URL", "sqlite:///bouesti_portal.db")
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login Setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None

# =========================================================================
# 2. DATABASE MODELS
# =========================================================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    matric_no = db.Column(db.String(50), unique=True, nullable=True)
    role = db.Column(db.String(20), nullable=False, default='Student') # Roles: Student, Admin
    password_hash = db.Column(db.String(255), nullable=False)
    
    complaints = db.relationship('Complaint', backref='student', lazy=True)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    complaints = db.relationship('Complaint', backref='category', lazy=True)

class Complaint(db.Model):
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False, default='Normal') # Urgent, High, Normal
    status = db.Column(db.String(30), nullable=False, default='Submitted') # Submitted, Under Review, Resolved, Rejected
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

# =========================================================================
# 3. ROUTES & CONTROLLERS
# =========================================================================
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = str(request.form.get('email', '')).strip()
        password = str(request.form.get('password', ''))
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard' if user.role == 'Admin' else 'student_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        full_name = str(request.form.get('full_name', '')).strip()
        email = str(request.form.get('email', '')).strip()
        matric_no = str(request.form.get('matric_no', '')).strip()
        password = str(request.form.get('password', ''))
        
        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'danger')
            return render_template('register.html')
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
            full_name=full_name,
            email=email,
            matric_no=matric_no,
            role='Student',
            password_hash=hashed_pw
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'Student':
        return redirect(url_for('admin_dashboard'))
    complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.submission_date.desc()).all()
    return render_template('student/dashboard.html', complaints=complaints)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'Admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    query = str(request.args.get('q', '')).strip()
    status_filter = str(request.args.get('status', '')).strip()
    
    complaints_query = Complaint.query
    
    if status_filter:
        complaints_query = complaints_query.filter(Complaint.status == status_filter)
        
    if query:
        search_pattern = f"%{query}%"
        complaints_query = complaints_query.join(User, Complaint.user_id == User.id).filter(
            (Complaint.reference_number.ilike(search_pattern)) |
            (Complaint.subject.ilike(search_pattern)) |
            (User.full_name.ilike(search_pattern)) |
            (User.matric_no.ilike(search_pattern))
        )
        
    complaints = complaints_query.order_by(Complaint.submission_date.desc()).all()
    return render_template('admin/dashboard.html', complaints=complaints)

# =========================================================================
# 4. SAFE BOOTSTRAPPER WITH CASCADE TABLE RE-SYNC
# =========================================================================
@app.before_request
def ensure_db_initialized():
    if getattr(app, '_db_initialized', False):
        return

    try:
        # Create missing tables
        db.create_all()

        # Check if users table needs schema sync
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        if 'users' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('users')]
            if 'matric_no' not in columns:
                # Force CASCADE drop on PostgreSQL to clear dependent tables safely
                with db.engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS status_history CASCADE;"))
                    conn.execute(text("DROP TABLE IF EXISTS complaints CASCADE;"))
                    conn.execute(text("DROP TABLE IF EXISTS categories CASCADE;"))
                    conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
                db.create_all()

        # Seed Default Complaint Categories
        default_categories = [
            "Academic Affairs",
            "Bursary & Payments",
            "Hostel & Accommodation",
            "Library Services",
            "ICT & Portal Issues",
            "Facilities & Infrastructure",
            "General Misconduct / Security",
            "Other Enquiries"
        ]

        for cat_name in default_categories:
            if not Category.query.filter_by(name=cat_name).first():
                db.session.add(Category(name=cat_name))
        db.session.commit()

        # Seed Default Admin Account
        admin_email = "admin@bouesti.edu.ng"
        if not User.query.filter_by(email=admin_email).first():
            hashed_password = generate_password_hash("Admin@BOUESTI2026!", method="pbkdf2:sha256")
            admin_user = User(
                full_name="System Super Administrator",
                email=admin_email,
                matric_no="ADMIN/001",
                role="Admin",
                password_hash=hashed_password
            )
            db.session.add(admin_user)
            db.session.commit()

        app._db_initialized = True
    except Exception as e:
        db.session.rollback()
        print(f"Database Initialization Note: {e}")

# =========================================================================
# 5. ENTRY POINT
# =========================================================================
if __name__ == '__main__':
    app.run(debug=True)