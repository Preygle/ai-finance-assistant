#!/usr/bin/env python3
"""
AI-Powered Finance Assistant - Application Runner

This script helps you run the Flask application with all the necessary setup.
"""

import subprocess
import sys
import os
import argparse

def install_requirements():
    """Install required packages from requirements.txt"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("All packages installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")
        return False
    return True

def run_migrations():
    """Run database migrations"""
    print("Running database migrations...")
    try:
        subprocess.check_call([sys.executable, "-m", "flask", "db", "upgrade"])
        print("Database migrations completed!")
    except subprocess.CalledProcessError as e:
        print(f"Error running migrations: {e}")
        return False
    return True

def run_app():
    """Run the Flask application"""
    print("Starting the AI-Powered Finance Assistant...")
    print("Application will be available at: http://localhost:5000")
    print("Features available:")
    print("   - User registration and login with JWT tokens")
    print("   - Secure password hashing with bcrypt")
    print("   - CSRF protection")
    print("   - Modern responsive UI")
    print("   - Dashboard for authenticated users")
    print("   - CSV transaction upload with preview")
    print("   - Plaid bank integration (simulated)")
    print("   - Transaction viewing with Indian Rupee formatting")
    print("   - Financial summary and filtering")
    print("\nSample CSV file available: sample_transactions.csv")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        subprocess.run([sys.executable, "app.py"])
    except KeyboardInterrupt:
        print("\nApplication stopped. Goodbye!")

def reset_transactions():
    """Reset the transaction database"""
    print("Resetting the transaction database...")
    try:
        subprocess.check_call([sys.executable, "-m", "flask", "reset-transactions"])
    except subprocess.CalledProcessError as e:
        print(f"Error resetting the database: {e}")
        return False
    return True

def main():
    """Main function to set up and run the application"""
    parser = argparse.ArgumentParser(description='AI-Powered Finance Assistant')
    parser.add_argument('--reset-transactions', action='store_true', help='Reset the transaction database')
    args = parser.parse_args()

    print("AI-Powered Finance Assistant Setup")
    print("=" * 50)
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Virtual environment detected")
    else:
        print("Warning: No virtual environment detected. Consider using a virtual environment.")
    
    # Install requirements
    if not install_requirements():
        print("Failed to install requirements. Please check your Python environment.")
        return
    
    # Set Flask environment variables
    os.environ['FLASK_APP'] = 'manage.py'
    os.environ['FLASK_ENV'] = 'development'
    
    if args.reset_transactions:
        reset_transactions()
        return
    
    # Run migrations
    if not run_migrations():
        print("Failed to run migrations. Please check your database configuration.")
        return
    
    # Run the application
    run_app()

if __name__ == "__main__":
    main()
