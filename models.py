from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to transactions
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    merchant = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # Amount in INR
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), nullable=False)  # 'csv' or 'plaid'
    plaid_transaction_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert transaction to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'merchant': self.merchant,
            'amount': self.amount,
            'category': self.category,
            'description': self.description,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Transaction {self.merchant} - ₹{self.amount}>'

class AIModelStorage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(128), unique=True, nullable=False)
    model_blob = db.Column(db.LargeBinary, nullable=False)


class IntegrityProof(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    txn_hash = db.Column(db.String(128), nullable=False)  # SHA-256 hex
    chain_tx_hash = db.Column(db.String(128), nullable=True)
    chain = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TransactionAIFiltered(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    ai_confidence = db.Column(db.Float, nullable=True)
    ai_flag = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    transaction = db.relationship('Transaction', backref=db.backref('ai_filtered', lazy=True))
