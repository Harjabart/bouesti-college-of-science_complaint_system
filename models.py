from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Student') # Roles: Student, Admin, SuperAdmin
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    complaints = db.relationship('Complaint', backref='student', lazy=True)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False) # e.g., Academic Issues, Laboratory Concerns[cite: 1]
    description = db.Column(db.Text, nullable=True)

    # Relationships
    complaints = db.relationship('Complaint', backref='category', lazy=True)

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False) # e.g., CSC-2026-0045[cite: 1]
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Submitted') # Submitted, Under Review, Referred, Action Taken, Resolved, Rejected[cite: 1]
    priority = db.Column(db.String(10), default='Normal')
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    status_history = db.relationship('StatusHistory', backref='complaint', cascade="all, delete-orphan", lazy=True)

class StatusHistory(db.Model):
    __tablename__ = 'status_history'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    previous_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    change_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)