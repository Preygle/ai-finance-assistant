# AI-Powered Finance Assistant - Authentication System

## Overview

This document describes the authentication system implemented for the AI-Powered Finance Assistant, following the requirements specified in GEMINI.md.

## Features Implemented

### 1. User Authentication (FR1)
- ✅ User registration and login via web interface
- ✅ Password hashing with bcrypt (via Werkzeug)
- ✅ JWT tokens with 30-minute timeout
- ✅ CSRF protection for all form submissions
- ✅ Auto-expire sessions after inactivity
- ✅ Secure password validation

### 2. Security Features
- ✅ Password strength validation (minimum 6 characters)
- ✅ Username and email uniqueness validation
- ✅ Secure session management
- ✅ Flash message system for user feedback
- ✅ Responsive design for all devices

### 3. User Interface
- ✅ Modern, responsive design with gradient backgrounds
- ✅ Professional navigation bar with user status
- ✅ Beautiful authentication forms with icons
- ✅ Dashboard for authenticated users
- ✅ Different homepage content for authenticated/non-authenticated users

## File Structure

```
├── app.py                 # Main Flask application with auth routes
├── models.py             # User model with password hashing
├── config.py             # Configuration including JWT settings
├── requirements.txt      # Updated with auth dependencies
├── templates/
│   ├── base.html         # Base template with navigation
│   ├── index.html        # Homepage (different for auth/unauth users)
│   ├── login.html        # Login form
│   ├── register.html     # Registration form
│   └── dashboard.html    # User dashboard
├── static/
│   └── style.css         # Complete styling for all components
└── run_app.py           # Helper script to run the application
```

## Dependencies Added

- `Flask-JWT-Extended` - JWT token management
- `Flask-Login` - User session management
- `bcrypt` - Password hashing (via Werkzeug)

## Database Schema

### User Table
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    is_active BOOLEAN DEFAULT 1
);
```

## API Endpoints

### Authentication Routes
- `GET /register` - Registration form
- `POST /register` - Process registration
- `GET /login` - Login form
- `POST /login` - Process login
- `GET /logout` - Logout user
- `POST /refresh` - Refresh JWT token

### Protected Routes
- `GET /` - Homepage (different content for auth/unauth)
- `GET /dashboard` - User dashboard (requires authentication)
- `GET /upload` - Upload page (requires authentication)

## Usage Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python run_app.py
```
Or manually:
```bash
python app.py
```

### 3. Access the Application
- Open your browser to `http://localhost:5000`
- Register a new account or login with existing credentials
- Explore the dashboard and features

## Security Considerations

### Password Security
- Passwords are hashed using Werkzeug's `generate_password_hash()`
- Uses PBKDF2 with SHA256 by default
- No plain text passwords are stored

### JWT Token Security
- 30-minute access token expiration
- 30-day refresh token expiration
- Tokens are used for API authentication
- CSRF protection on all forms

### Session Management
- Flask-Login handles user sessions
- Automatic session cleanup on logout
- "Remember me" functionality available

## Configuration

### Environment Variables
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key
- `DATABASE_URL` - Database connection string

### Default Configuration
- SQLite database for development
- JWT tokens expire in 30 minutes
- CSRF protection enabled
- Debug mode enabled in development

## Next Steps

The authentication system is now complete and ready for integration with the AI features described in GEMINI.md:

1. **Transaction Ingestion (FR2)** - Upload and process transaction data
2. **AI Categorization (FR3)** - Machine learning for transaction categorization
3. **Fraud Detection (FR3 Extension)** - Anomaly detection for suspicious transactions
4. **Budgeting & Suggestions (FR4)** - AI-powered financial recommendations
5. **Blockchain Integrity Logging (FR5)** - Ethereum-based transaction verification

## Testing the Authentication

### Registration Test
1. Go to `/register`
2. Fill in username, email, and password
3. Submit the form
4. Check for success message and redirect to login

### Login Test
1. Go to `/login`
2. Enter valid credentials
3. Check for successful login and redirect to homepage
4. Verify navigation shows user-specific content

### Logout Test
1. While logged in, click logout
2. Verify redirect to homepage
3. Check that navigation shows login/register options

## Troubleshooting

### Common Issues
1. **Database errors**: Ensure SQLite database is writable
2. **Import errors**: Install all requirements with `pip install -r requirements.txt`
3. **CSRF errors**: Ensure forms include `{{ csrf_token() }}`
4. **JWT errors**: Check JWT_SECRET_KEY configuration

### Debug Mode
The application runs in debug mode by default. For production:
1. Set `FLASK_ENV=production`
2. Use a strong SECRET_KEY
3. Configure proper database
4. Disable debug mode

## Support

For issues or questions about the authentication system, refer to:
- Flask documentation: https://flask.palletsprojects.com/
- Flask-Login documentation: https://flask-login.readthedocs.io/
- Flask-JWT-Extended documentation: https://flask-jwt-extended.readthedocs.io/


