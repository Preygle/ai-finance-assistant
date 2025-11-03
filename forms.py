from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp
from models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=20, message='Username must be between 3 and 20 characters'),
        Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
               'Username must have only letters, '
               'numbers, dots or underscores')
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Account')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class CSVUploadForm(FlaskForm):
    csv_file = FileField('CSV File', validators=[
        FileRequired(),
        FileAllowed(['csv'], 'Only CSV files are allowed!')
    ])
    submit = SubmitField('Upload & Preview')

class CSVProcessForm(FlaskForm):
    date_column = SelectField('Date Column', validators=[DataRequired()])
    merchant_column = SelectField('Merchant Column', validators=[DataRequired()])
    amount_column = SelectField('Amount Column', validators=[DataRequired()])
    category_column = SelectField('Category Column')
    currency = SelectField('Original Currency', 
                         choices=[('INR', 'Indian Rupee (INR)'),
                                 ('USD', 'US Dollar (USD)'),
                                 ('EUR', 'Euro (EUR)'),
                                 ('GBP', 'British Pound (GBP)')],
                         default='INR')
    submit = SubmitField('Process Transactions')

class ReceiptUploadForm(FlaskForm):
    receipt_file = FileField('Receipt File', validators=[
        FileRequired(),
        FileAllowed(['png', 'jpg', 'jpeg', 'pdf'], 'Only image or PDF files are allowed!')
    ])
    submit = SubmitField('Upload and Analyze')