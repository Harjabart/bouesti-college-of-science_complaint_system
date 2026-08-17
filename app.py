import os
import random
import string
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Category, Complaint, StatusHistory

app = Flask(__name__)
app.config.from_object(Config)

# --- Flask-Mail Configuration (SSL Port 465) ---
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'joshuatemiladechoice@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-16-char-app-password')
app.config['MAIL_DEFAULT_SENDER'] = (
    'BOUESTI Complaint Portal',
    os.environ.get('MAIL_USERNAME', 'joshuatemiladechoice@gmail.com')
)

mail = Mail(app)

# --- Initialize Database & Login Manager ---
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Restricted List of College of Science Departments
COLLEGE_OF_SCIENCE_DEPTS = [
    'Computer Science',
    'Biochemistry',
    'Microbiology',
    'Industrial Chemistry',
    'Physics with Electronics',
    'Mathematics & Statistics'
]

@login_manager.user_loader
def load_user(user_id):
    # Modern SQLAlchemy 2.0 lookup syntax
    return db.session.get(User, int(user_id))

# Admin Access Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['Admin', 'SuperAdmin']:
            flash('Access denied. Administrator privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def generate_reference_number():
    year = datetime.now().year
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BOUESTI-{year}-{random_str}"

def send_status_email(student_email, student_name, ref_no, status, notes=""):
    # Guard against unconfigured placeholder email
    if not app.config['MAIL_USERNAME'] or app.config['MAIL_USERNAME'] == 'your-email@gmail.com':
        print("[Flask-Mail] Skipping email delivery: Configured email is still placeholder.")
        return

    try:
        msg = Message(
            subject=f"[BOUESTI Complaint Portal] Update on {ref_no}",
            recipients=[student_email]
        )
        msg.body = f"""Hello {student_name},

Your complaint logged with Reference ID: {ref_no} has been updated.

Current Status: {status}
Admin Remarks: {notes if notes else 'No additional notes provided.'}

You can track your real-time complaint status anytime on the BOUESTI Complaint Portal.

Best regards,
College of Science Administrative Team
Bamidele Olumilua University of Education, Science and Technology, Ikere-Ekiti
"""
        mail.send(msg)
        print(f"[Flask-Mail] Status email sent successfully to {student_email}")
    except Exception as e:
        print(f"[Flask-Mail] Email delivery failed: {e}")

def seed_default_categories_and_admin():
    default_categories = [
        'Academic Issues',
        'Laboratory Concerns',
        'Administrative Matters',
        'Student Welfare'
    ]
    for cat_name in default_categories:
        if not db.session.execute(db.select(Category).filter_by(name=cat_name)).scalar_one_or_none():
            db.session.add(Category(name=cat_name))
    
    # Pre-seed default Admin account if none exists
    admin_exists = db.session.execute(db.select(User).filter_by(username='admin')).scalar_one_or_none()
    if not admin_exists:
        hashed_admin_pw = generate_password_hash('AdminPass2026!', method='scrypt')
        admin_user = User(
            full_name='System Administrator',
            email='admin@bouesti.edu.ng',
            username='admin',
            password_hash=hashed_admin_pw,
            role='Admin'
        )
        db.session.add(admin_user)
    
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_default_categories_and_admin()

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/track', methods=['GET', 'POST'])
def track_complaint():
    complaint = None
    searched_ref = None
    
    if request.method == 'POST':
        searched_ref = request.form.get('reference_number', '').strip()
        if searched_ref:
            complaint = db.session.execute(
                db.select(Complaint).filter_by(reference_number=searched_ref)
            ).scalar_one_or_none()
            if not complaint:
                flash(f'No complaint found with Reference ID: {searched_ref}', 'error')

    return render_template('track.html', complaint=complaint, searched_ref=searched_ref)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email', '').lower().strip()
        username = request.form.get('username')
        department = request.form.get('department')
        password = request.form.get('password')

        # 1. Enforce College of Science restriction
        if department not in COLLEGE_OF_SCIENCE_DEPTS:
            flash('Access restricted: Only College of Science students can register.', 'error')
            return redirect(url_for('register'))

        # 2. Enforce BOUESTI institutional email domain validation
        if not email.endswith('@bouesti.edu.ng'):
            flash('Registration failed: You must use an official @bouesti.edu.ng email address.', 'error')
            return redirect(url_for('register'))

        existing_user = db.session.execute(
            db.select(User).filter((User.email == email) | (User.username == username))
        ).scalar_one_or_none()

        if existing_user:
            flash('Email or Username already exists in the system.', 'error')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(
            full_name=full_name,
            email=email,
            username=username,
            password_hash=hashed_pw,
            role='Student'
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in to continue.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', departments=COLLEGE_OF_SCIENCE_DEPTS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role in ['Admin', 'SuperAdmin']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'Welcome back, {user.full_name}!', 'success')
            if user.role in ['Admin', 'SuperAdmin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- STUDENT ROUTES ---

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role in ['Admin', 'SuperAdmin']:
        return redirect(url_for('admin_dashboard'))
    
    user_complaints = db.session.execute(
        db.select(Complaint)
        .filter_by(student_id=current_user.id)
        .order_by(Complaint.submission_date.desc())
    ).scalars().all()

    return render_template('student/dashboard.html', complaints=user_complaints)

@app.route('/submit-complaint', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    categories = db.session.execute(db.select(Category)).scalars().all()

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        subject = request.form.get('subject')
        description = request.form.get('description')
        priority = request.form.get('priority', 'Normal')

        ref_no = generate_reference_number()

        new_complaint = Complaint(
            reference_number=ref_no,
            student_id=current_user.id,
            category_id=category_id,
            subject=subject,
            description=description,
            priority=priority,
            status='Submitted'
        )
        db.session.add(new_complaint)
        db.session.commit()

        history = StatusHistory(
            complaint_id=new_complaint.id,
            previous_status=None,
            new_status='Submitted',
            changed_by_id=current_user.id,
            notes='Complaint logged into system.'
        )
        db.session.add(history)
        db.session.commit()

        # Send automated email notification
        send_status_email(
            student_email=current_user.email,
            student_name=current_user.full_name,
            ref_no=ref_no,
            status='Submitted',
            notes='Your complaint has been logged and assigned to the administration.'
        )

        flash(f'Complaint submitted successfully! Your Reference ID is {ref_no}', 'success')
        return redirect(url_for('dashboard'))

    return render_template('student/submit_complaint.html', categories=categories)

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_complaints = db.session.query(Complaint).count()
    pending_complaints = db.session.query(Complaint).filter(Complaint.status.in_(['Submitted', 'Under Review'])).count()
    resolved_complaints = db.session.query(Complaint).filter_by(status='Resolved').count()

    all_complaints = db.session.execute(
        db.select(Complaint).order_by(Complaint.submission_date.desc())
    ).scalars().all()

    return render_template('admin/dashboard.html', 
                           complaints=all_complaints,
                           total=total_complaints,
                           pending=pending_complaints,
                           resolved=resolved_complaints)

@app.route('/admin/complaint/<int:complaint_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_view_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        flash('Complaint not found.', 'error')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        new_status = request.form.get('status')
        admin_notes = request.form.get('notes')

        if new_status and new_status != complaint.status:
            prev_status = complaint.status
            complaint.status = new_status
            complaint.last_update = datetime.utcnow()

            history = StatusHistory(
                complaint_id=complaint.id,
                previous_status=prev_status,
                new_status=new_status,
                changed_by_id=current_user.id,
                notes=admin_notes
            )
            db.session.add(history)
            db.session.commit()

            # Trigger email notification to the student on status update
            send_status_email(
                student_email=complaint.student.email,
                student_name=complaint.student.full_name,
                ref_no=complaint.reference_number,
                status=new_status,
                notes=admin_notes
            )

            flash(f'Status for {complaint.reference_number} updated to "{new_status}".', 'success')
            return redirect(url_for('admin_view_complaint', complaint_id=complaint.id))

    return render_template('admin/view_complaint.html', complaint=complaint)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)