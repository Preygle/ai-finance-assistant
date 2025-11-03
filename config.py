import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration (30-minute access, 30-day refresh)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or os.urandom(24)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Privacy & Login configuration
    PRIVACY_MODE = os.environ.get('PRIVACY_MODE', 'false').lower() == 'true'
    LOGIN_DISABLED = False