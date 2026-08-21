import os
import uuid
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer as Serializer

# =========================================================================
# 1. APPLICATION & DATABASE CONFIGURATION
# =========================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bouesti-secret-key-2026-production')

# Mail Configuration (Gmail SMTP)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# File Upload Configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

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

    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except Exception:
            return None
        return db.session.get(User, user_id)

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
    priority = db.Column(db.String(20), nullable=False, default='Normal')
    status = db.Column(db.String(30), nullable=False, default='Submitted')
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    attachment = db.Column(db.String(255), nullable=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

# =========================================================================
# HELPER FUNCTIONS
# =========================================================================
def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message(
        'BOUESTI Student Portal - Password Reset Request',
        sender=app.config['MAIL_USERNAME'],
        recipients=[user.email]
    )
    reset_url = url_for('reset_token', token=token, _external=True)
    msg.body = f'''To reset your password for the BOUESTI Student Complaint Portal, please visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.
Note: This link is valid for 30 minutes.

Best regards,
BOUESTI Complaint Management Team
'''
    mail.send(msg)

# =========================================================================
# 3. ROUTES & CONTROLLERS
# =========================================================================
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return render_template('index.html')

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

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = str(request.form.get('email', '')).strip()
        user = User.query.filter_by(email=email).first()
        
        if user:
            try:
                send_reset_email(user)
                flash('An email has been sent with instructions to reset your password.', 'info')
            except Exception as e:
                print(f"SMTP EXCEPTION: {e}")  # Logs error to Render console
                flash('Unable to send reset email at this moment. Please check network settings.', 'danger')
        else:
            # Flashing the same message prevents email enumeration/security leaks
            flash('An email has been sent with instructions to reset your password.', 'info')
            
        return redirect(url_for('login'))
        
    return render_template('reset_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token. Please request a new password reset.', 'danger')
        return redirect(url_for('reset_request'))
    
    if request.method == 'POST':
        password = str(request.form.get('password', ''))
        confirm_password = str(request.form.get('confirm_password', ''))
        
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'warning')
            return render_template('reset_token.html')
            
        user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_token.html')

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
# ALL PREVIOUSLY MISSING ROUTES (FIXES URL_FOR BUILDERRORS)
# =========================================================================

@app.route('/complaint/submit', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    categories = Category.query.all()
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        subject = str(request.form.get('subject', '')).strip()
        details = str(request.form.get('details', '')).strip()
        priority = request.form.get('priority', 'Normal')
        
        file = request.files.get('attachment')
        filename = None
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4().hex}{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        ref_no = f"CMP-{uuid.uuid4().hex[:8].upper()}"
        
        new_complaint = Complaint(
            reference_number=ref_no,
            subject=subject,
            details=details,
            priority=priority,
            category_id=category_id,
            user_id=current_user.id,
            attachment=filename
        )
        db.session.add(new_complaint)
        db.session.commit()
        
        flash(f'Complaint submitted successfully! Your Ref ID is {ref_no}', 'success')
        return redirect(url_for('student_dashboard'))
        
    return render_template('student/submit_complaint.html', categories=categories)

@app.route('/track', methods=['GET', 'POST'])
def track_complaint():
    complaint = None
    if request.method == 'POST':
        ref_no = str(request.form.get('reference_number', '')).strip().upper()
        complaint = Complaint.query.filter_by(reference_number=ref_no).first()
        if not complaint:
            flash('No complaint found with that Reference Number.', 'danger')
    return render_template('track.html', complaint=complaint)

@app.route('/admin/complaint/<int:complaint_id>')
@login_required
def view_complaint(complaint_id):
    if current_user.role != 'Admin':
        return redirect(url_for('student_dashboard'))
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        flash('Complaint not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/view_complaint.html', complaint=complaint)

@app.route('/admin/complaint/<int:complaint_id>/status', methods=['POST'])
@login_required
def update_complaint_status(complaint_id):
    if current_user.role != 'Admin':
        return redirect(url_for('student_dashboard'))
    complaint = db.session.get(Complaint, complaint_id)
    if complaint:
        new_status = request.form.get('status')
        if new_status:
            complaint.status = new_status
            db.session.commit()
            flash('Complaint status updated successfully.', 'success')
    return redirect(url_for('view_complaint', complaint_id=complaint_id))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =========================================================================
# 4. SAFE BOOTSTRAPPER (Runs once at app start, not per request)
# =========================================================================
def init_db():
    with app.app_context():
        try:
            db.create_all()

            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                columns = [c['name'] for c in inspector.get_columns('users')]
                if 'matric_no' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text("DROP TABLE IF EXISTS status_history CASCADE;"))
                        conn.execute(text("DROP TABLE IF EXISTS complaints CASCADE;"))
                        conn.execute(text("DROP TABLE IF EXISTS categories CASCADE;"))
                        conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
                    db.create_all()

            default_categories = [
                "Academic Affairs", "Bursary & Payments", "Hostel & Accommodation",
                "Library Services", "ICT & Portal Issues", "Facilities & Infrastructure",
                "General Misconduct / Security", "Other Enquiries"
            ]

            for cat_name in default_categories:
                if not Category.query.filter_by(name=cat_name).first():
                    db.session.add(Category(name=cat_name))
            db.session.commit()

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

        except Exception as e:
            db.session.rollback()
            print(f"Database Initialization Note: {e}")

# Initialize once on startup
init_db()

# =========================================================================
# 5. ENTRY POINT
# =========================================================================
if __name__ == '__main__':
    app.run(debug=True)