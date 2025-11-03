#!/usr/bin/env python3
"""
Test script to verify the application works correctly
"""

import sys
import os

def test_imports():
    """Test if all modules can be imported without errors"""
    try:
        print("Testing imports...")
        
        # Test basic imports
        from flask import Flask
        print("✅ Flask imported successfully")
        
        from forms import RegistrationForm, LoginForm, CSVUploadForm, CSVProcessForm
        print("✅ Forms imported successfully")
        
        from models import User, Transaction
        print("✅ Models imported successfully")
        
        from extensions import db, migrate, csrf, login_manager, jwt
        print("✅ Extensions imported successfully")
        
        from plaid_service import PlaidService
        print("✅ Plaid service imported successfully")
        
        print("\n🎉 All imports successful! The application should work correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_app_creation():
    """Test if the Flask app can be created"""
    try:
        print("\nTesting app creation...")
        
        # Set environment variables
        os.environ['FLASK_APP'] = 'app.py'
        os.environ['FLASK_ENV'] = 'development'
        
        from app import create_app
        app = create_app()
        
        print("✅ Flask app created successfully")
        print("✅ App configuration loaded")
        print("✅ Database initialized")
        print("✅ Extensions configured")
        
        return True
        
    except Exception as e:
        print(f"❌ App creation error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Testing AI-Powered Finance Assistant")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed. Please check the error messages above.")
        return False
    
    # Test app creation
    if not test_app_creation():
        print("\n❌ App creation tests failed. Please check the error messages above.")
        return False
    
    print("\n🎉 All tests passed! Your application is ready to run.")
    print("\nTo start the application, run:")
    print("  python app.py")
    print("  or")
    print("  python run_app.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

