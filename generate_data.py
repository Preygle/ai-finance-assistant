import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Plaid-like categories
CATEGORIES = {
    'Income': {
        'merchants': ['Salary Credit', 'Freelance Payment', 'Consulting Fee', 'Dividend Credit', 'Rental Income'],
        'amount_range': (30000, 80000)
    },
    'Shopping': {
        'merchants': ['Amazon', 'Flipkart', 'Myntra', 'Big Bazaar', 'D-Mart', 'Reliance Retail'],
        'amount_range': (500, 5000)
    },
    'Food and Dining': {
        'merchants': ['Swiggy', 'Zomato', 'Dominos', 'McDonald\'s', 'Starbucks', 'Food Panda'],
        'amount_range': (200, 2000)
    },
    'Transportation': {
        'merchants': ['Uber', 'Ola', 'Metro Card Recharge', 'Petrol Pump', 'Indian Railways'],
        'amount_range': (100, 3000)
    },
    'Bills and Utilities': {
        'merchants': ['Electricity Board', 'Water Supply', 'Airtel', 'Jio', 'BSNL', 'Tata Power'],
        'amount_range': (500, 5000)
    },
    'Entertainment': {
        'merchants': ['Netflix', 'Amazon Prime', 'PVR Cinemas', 'BookMyShow', 'Spotify'],
        'amount_range': (199, 1999)
    },
    'Health and Fitness': {
        'merchants': ['Apollo Pharmacy', 'Gym Membership', 'Medical Store', 'Diagnostic Center'],
        'amount_range': (500, 5000)
    },
    'Education': {
        'merchants': ['Coursera', 'Udemy', 'School Fees', 'Book Store', 'Stationary Shop'],
        'amount_range': (500, 15000)
    }
}

def generate_year_transactions(start_date=None):
    if not start_date:
        start_date = datetime.now() - timedelta(days=365)
    
    transactions = []
    
    # Generate regular monthly income
    current_date = start_date
    monthly_salary = random.randint(45000, 65000)
    
    while current_date < datetime.now():
        # Monthly salary
        salary_date = current_date.replace(day=7)  # Salary on 7th
        transactions.append({
            'Date': salary_date.strftime('%Y-%m-%d'),
            'Merchant': 'Salary Credit',
            'Amount': monthly_salary,
            'Category': 'Income',
            'Description': 'Monthly Salary Credit'
        })
        
        # Generate 30-40 transactions per month
        num_transactions = random.randint(30, 40)
        
        for _ in range(num_transactions):
            category = random.choice(list(CATEGORIES.keys()))
            if category != 'Income':  # We already handled income
                merchant = random.choice(CATEGORIES[category]['merchants'])
                amount = round(random.uniform(*CATEGORIES[category]['amount_range']), 2)
                # Make it negative since it's an expense
                amount = -amount
                
                transaction_date = current_date + timedelta(days=random.randint(1, 30))
                if transaction_date < datetime.now():
                    transactions.append({
                        'Date': transaction_date.strftime('%Y-%m-%d'),
                        'Merchant': merchant,
                        'Amount': amount,
                        'Category': category,
                        'Description': f'Purchase at {merchant}'
                    })
        
        current_date = current_date + timedelta(days=30)
    
    # Convert to DataFrame and sort by date
    df = pd.DataFrame(transactions)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    
    return df

def add_seasonal_transactions(df):
    """Add festival season and holiday expenses"""
    # Diwali shopping (October)
    diwali_date = datetime(2024, 10, 15)
    df = pd.concat([df, pd.DataFrame([{
        'Date': pd.to_datetime(diwali_date),  # Convert to pandas datetime
        'Merchant': 'Big Bazaar',
        'Amount': -random.randint(15000, 25000),
        'Category': 'Shopping',
        'Description': 'Diwali Shopping'
    }])], ignore_index=True)
    
    # Year-end vacation (December)
    vacation_date = datetime(2024, 12, 20)
    df = pd.concat([df, pd.DataFrame([{
        'Date': pd.to_datetime(vacation_date),  # Convert to pandas datetime
        'Merchant': 'MakeMyTrip',
        'Amount': -random.randint(30000, 50000),
        'Category': 'Travel',
        'Description': 'Year-end Vacation Booking'
    }])], ignore_index=True)
    
    return df

if __name__ == "__main__":
    # Generate base transactions
    start_date = datetime(2024, 1, 1)  # Start from January 2024
    df = generate_year_transactions(start_date)
    
    # Add seasonal expenses
    df = add_seasonal_transactions(df)
    
    # Sort by date
    df = df.sort_values('Date')
    
    # Save to CSV
    output_file = 'transactions_2024.csv'  # Changed file path
    df.to_csv(output_file, index=False)
    print(f"Generated {len(df)} transactions and saved to {output_file}")
    
    # Print some statistics
    print("\nDataset Statistics:")
    print(f"Date Range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"Total Income: ₹{df[df['Amount'] > 0]['Amount'].sum():,.2f}")
    print(f"Total Expenses: ₹{abs(df[df['Amount'] < 0]['Amount'].sum()):,.2f}")
    print("\nCategory-wise Breakdown:")
    print(df.groupby('Category')['Amount'].sum().sort_values())