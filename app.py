import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Secret key & Configuration
app.config['SECRET_KEY'] = 'bouesti-complaint-portal-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Upload Folder Path
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Helper function to generate unique Reference ID (e.g., BOUESTI-8F92A)
def generate_ref_id():
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(random.choices(chars, k=5))
    return f"BOUESTI-{random_str}"


# =========================================================================
# DATABASE MODELS
# =========================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    matric_no = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    complaints = db.relationship('Complaint', backref='user', lazy=True)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False, default='General')
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================================================================
# INITIALIZATION (AUTO-CREATE DB & ADMIN USER)
# =========================================================================

with app.app_context():
    db.create_all()
    
    # Auto-seed Default Admin Account if it doesn't exist
    admin_email = "admin@bouesti.edu.ng"
    existing_admin = User.query.filter_by(email=admin_email).first()
    if not existing_admin:
        default_admin = User(
            full_name="Portal Administrator",
            email=admin_email,
            matric_no="ADMIN/001",
            password=generate_password_hash("admin123"),
            is_admin=True
        )
        db.session.add(default_admin)
        db.session.commit()
        print("Default admin account created: admin@bouesti.edu.ng / admin123")


# =========================================================================
# GENERAL & FILE ROUTES
# =========================================================================

@app.route('/')
def home():
    return render_template('index.html')

# Route to serve uploaded evidence attachments safely
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =========================================================================
# AUTHENTICATION ROUTES
# =========================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        matric_no = request.form.get('matric_no')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email address is already registered.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            full_name=full_name,
            email=email,
            matric_no=matric_no,
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
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid login credentials.', 'danger')

    return render_template('login.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if user.is_admin:
                login_user(user)
                flash('Welcome to Admin Portal', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Access denied. Account lacks administrator privileges.', 'danger')
        else:
            flash('Invalid admin credentials.', 'danger')

    return render_template('admin/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# =========================================================================
# STUDENT ROUTES
# =========================================================================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))

    complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    return render_template('student/dashboard.html', complaints=complaints)


@app.route('/student/submit-complaint', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    if request.method == 'POST':
        category = request.form.get('category', 'General')
        title = request.form.get('title')
        description = request.form.get('description')
        
        filename = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '' and allowed_file(file.filename):
                saved_filename = secure_filename(file.filename)
                unique_prefix = datetime.now().strftime('%Y%m%d%H%M%S_')
                final_filename = unique_prefix + saved_filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_filename))
                filename = final_filename

        new_complaint = Complaint(
            reference_number=generate_ref_id(),
            category=category,
            title=title,
            description=description,
            filename=filename,
            user_id=current_user.id
        )

        db.session.add(new_complaint)
        db.session.commit()

        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student/submit_complaint.html')


# =========================================================================
# ADMIN ROUTES
# =========================================================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))

    # Retrieve all complaints ordered by most recent
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin/dashboard.html', complaints=complaints)


# Route function name matched with template: update_complaint_status
@app.route('/admin/update-status/<int:complaint_id>', methods=['POST'])
@login_required
def update_complaint_status(complaint_id):
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))

    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get('status')

    if new_status:
        complaint.status = new_status
        db.session.commit()
        flash(f'Status for complaint {complaint.reference_number} updated to "{new_status}".', 'success')

    return redirect(request.referrer or url_for('admin_dashboard'))


# =========================================================================
# RUN APPLICATION
# =========================================================================

if __name__ == '__main__':
    app.run(debug=True)