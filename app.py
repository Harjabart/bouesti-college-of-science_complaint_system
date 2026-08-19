import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration ---
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

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    matric_no = db.Column(db.String(50), unique=True, nullable=True)
    department = db.Column(db.String(100), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('complaints', lazy=True))

# Create tables inside app context safely
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database setup note: {e}")

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        matric_no = request.form.get('matric_no', '').strip()
        department = request.form.get('department', '').strip()
        password = request.form.get('password')

        # Flexible student email validation
        if not (email.endswith('bouesti.edu.ng') or '@bouesti.edu.ng' in email):
            flash('You cannot create an account because you are not recognized as a BOUESTI student.', 'danger')
            return redirect(url_for('register'))

        existing_user = User.query.filter((User.email == email) | (User.matric_no == matric_no)).first()
        if existing_user:
            flash('Email or Matriculation Number already registered.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
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

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('login'))
    
    complaints = Complaint.query.filter_by(user_id=session['user_id']).all()
    return render_template('student_dashboard.html', complaints=complaints)

@app.route('/submit_complaint', methods=['GET', 'POST'])
def submit_complaint():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        new_complaint = Complaint(
            title=title,
            description=description,
            user_id=session['user_id']
        )
        db.session.add(new_complaint)
        db.session.commit()

        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('submit_complaint.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    complaints = Complaint.query.all()
    return render_template('admin_dashboard.html', complaints=complaints)

@app.route('/admin/update_status/<int:complaint_id>', methods=['POST'])
def update_status(complaint_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get('status')
    complaint.status = new_status
    db.session.commit()

    # Send status notification email
    try:
        msg = Message(
            f"Complaint Status Update: {complaint.title}",
            recipients=[complaint.user.email]
        )
        msg.body = f"Hello {complaint.user.full_name},\n\nYour complaint titled '{complaint.title}' status has been updated to: {new_status}.\n\nBest regards,\nBOUESTI College of Science"
        mail.send(msg)
    except Exception as e:
        flash(f'Status updated, but email sending failed: {str(e)}', 'warning')

    flash('Complaint status updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)