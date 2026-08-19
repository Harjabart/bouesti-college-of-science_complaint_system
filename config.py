import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base Configuration"""
    # Security & Sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'bouest-college-of-science-secret-2026'

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'complaints.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File Upload Management
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}

    # Flask-Mail Settings (for email alerts)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME') or 'noreply@bouest.edu.ng'


class DevelopmentConfig(Config):
    """Development Configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production Configuration"""
    DEBUG = False
    # PostgreSQL database handling for deployment (e.g., Render/Heroku fix)
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = db_url.replace("postgres://", "postgresql://", 1)


# Configuration dictionary map
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}