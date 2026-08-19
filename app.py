import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename

# Import Configuration and Models
from config import config
from models import db, User, Category, Complaint, StatusHistory

app = Flask(__name__)

# Load Configuration Class based on Environment Variable
env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[env])

# Ensure Upload Folder Exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Extension Initializations
db.init_app(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_ref_id():
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(random.choices(chars, k=4))
    return f"CSC-{datetime.now().year}-{random_str}"

def send_status_email(user_email, ref_number, new_status, subject):
    """Sends a background email notification on status change if credentials are set."""
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        app.logger.info("Mail credentials missing. Skipping email dispatch.")
        return

    try:
        msg = Message(
            subject=f"Complaint Status Update: {ref_number}",
            recipients=[user_email]
        )
        msg.body = f"""Hello,

The status of your complaint "{subject}" (Ref: {ref_number}) has been updated to: {new_status}.

Log into the BOUESTI Complaint Portal to view full details and official remarks.

Best regards,
BOUESTI Complaint Resolution Office
"""
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Failed to send status update email: {str(e)}")

# Template Context Processor
@app.context_processor
def inject_globals():
    return {'datetime': datetime}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================================================================
# INITIALIZATION & DATABASE SEEDING
# =========================================================================

with app.app_context():
    db.create_all()

    # Seed Default Categories
    default_categories = [
        ('Academic Issues', 'Concerns related to grades, lectures, or academic records.'),
        ('Laboratory Concerns', 'Issues involving lab equipment, sessions, or practicals.'),
        ('Facilities & ICT', 'Complaints regarding portal access, network, or hardware.'),
        ('General Enquiry', 'Other institutional or administrative inquiries.')
    ]
    for cat_name, cat_desc in default_categories:
        if not Category.query.filter_by(name=cat_name).first():
            db.session.add(Category(name=cat_name, description=cat_desc))
    db.session.commit()

    # Seed Default Admin Account
    admin_email = "admin@bouesti.edu.ng"
    existing_admin = User.query.filter_by(email=admin_email).first()
    if not existing_admin:
        admin = User(
            full_name="Portal Administrator",
            email=admin_email,
            matric_no="ADMIN/001",
            role="SuperAdmin",
            is_admin=True
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Default admin account initialized: admin@bouesti.edu.ng / admin123")


# =========================================================================
# PUBLIC & FILE ROUTES
# =========================================================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =========================================================================
# AUTHENTICATION ROUTES
# =========================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        matric_no = request.form.get('matric_no', '').strip()
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email address is already registered.', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            full_name=full_name,
            email=email,
            matric_no=matric_no,
            role='Student',
            is_admin=False
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'student_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if user.is_admin or user.role in ['Admin', 'SuperAdmin']:
                session['is_admin'] = True
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid login credentials.', 'danger')

    return render_template('login.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.is_admin or user.role in ['Admin', 'SuperAdmin']:
                login_user(user)
                session['is_admin'] = True
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
    session.pop('is_admin', None)
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

    complaints = Complaint.query.filter_by(student_id=current_user.id).order_by(Complaint.submission_date.desc()).all()
    return render_template('student/dashboard.html', complaints=complaints)


@app.route('/student/submit-complaint', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))

    categories = Category.query.all()

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'Normal')
        
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
            student_id=current_user.id,
            category_id=int(category_id),
            subject=subject,
            description=description,
            priority=priority,
            filename=filename,
            status='Submitted'
        )

        db.session.add(new_complaint)
        db.session.flush()  # Obtain ID for status history

        # Record initial status in history
        history = StatusHistory(
            complaint_id=new_complaint.id,
            previous_status=None,
            new_status='Submitted',
            changed_by_id=current_user.id,
            notes='Initial complaint submission.'
        )
        db.session.add(history)
        db.session.commit()

        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student/submit_complaint.html', categories=categories)


# =========================================================================
# ADMIN ROUTES
# =========================================================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin and current_user.role not in ['Admin', 'SuperAdmin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))

    status_filter = request.args.get('status')
    search_query = request.args.get('q', '').strip()

    query = Complaint.query.join(User, Complaint.student_id == User.id)

    if status_filter:
        query = query.filter(Complaint.status == status_filter)

    if search_query:
        query = query.filter(
            (Complaint.reference_number.ilike(f"%{search_query}%")) |
            (Complaint.subject.ilike(f"%{search_query}%")) |
            (User.full_name.ilike(f"%{search_query}%")) |
            (User.matric_no.ilike(f"%{search_query}%"))
        )

    complaints = query.order_by(Complaint.submission_date.desc()).all()
    return render_template('admin/dashboard.html', complaints=complaints)


@app.route('/admin/complaint/<int:complaint_id>')
@login_required
def view_complaint(complaint_id):
    if not current_user.is_admin and current_user.role not in ['Admin', 'SuperAdmin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))

    complaint = Complaint.query.get_or_404(complaint_id)
    history = StatusHistory.query.filter_by(complaint_id=complaint.id).order_by(StatusHistory.change_date.desc()).all()
    return render_template('admin/view_complaint.html', complaint=complaint, history=history)


@app.route('/admin/update-status/<int:complaint_id>', methods=['POST'])
@login_required
def update_complaint_status(complaint_id):
    if not current_user.is_admin and current_user.role not in ['Admin', 'SuperAdmin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student_dashboard'))

    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    if new_status and new_status != complaint.status:
        old_status = complaint.status
        complaint.status = new_status

        # Create status change history entry
        history_entry = StatusHistory(
            complaint_id=complaint.id,
            previous_status=old_status,
            new_status=new_status,
            changed_by_id=current_user.id,
            notes=notes if notes else f"Status changed to {new_status}"
        )
        db.session.add(history_entry)
        db.session.commit()

        # Trigger background email dispatch
        send_status_email(complaint.student.email, complaint.reference_number, new_status, complaint.subject)

        flash(f'Status for {complaint.reference_number} updated to "{new_status}".', 'success')

    return redirect(request.referrer or url_for('admin_dashboard'))

# =========================================================================
# AUTOMATIC DATABASE BOOTSTRAPPER (For Render Free Tier)
# =========================================================================
def init_db_on_startup():
    with app.app_context():
        # Create all missing database tables
        db.create_all()

        # Seed Default Categories
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

        # Seed Default Admin
        admin_email = "admin@bouesti.edu.ng"
        if not User.query.filter_by(email=admin_email).first():
            hashed_password = generate_password_hash("Admin@BOUESTI2026!", method="scrypt")
            admin_user = User(
                full_name="System Super Administrator",
                email=admin_email,
                matric_number="ADMIN/001",
                role="Admin",
                password_hash=hashed_password
            )
            db.session.add(admin_user)

        db.session.commit()

# Execute database bootstrap
init_db_on_startup()

# =========================================================================
# RUN APPLICATION
# =========================================================================

if __name__ == '__main__':
    app.run()