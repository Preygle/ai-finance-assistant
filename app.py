from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Mock data
mock_balance = 10000.00
mock_budget = {
    "total": 2000.00,
    "spent": 1250.50
}
mock_transactions = [
    {"date": "2025-08-28", "category": "Groceries", "amount": -75.50, "description": "Supermarket run"},
    {"date": "2025-08-27", "category": "Salary", "amount": 2500.00, "description": "Monthly paycheck"},
    {"date": "2025-08-26", "category": "Utilities", "amount": -150.00, "description": "Electricity bill"},
    {"date": "2025-08-25", "category": "Entertainment", "amount": -45.00, "description": "Movie tickets"},
]
mock_goals = []

@app.route('/')
def home():
    budget_progress = (mock_budget["spent"] / mock_budget["total"]) * 100
    return render_template('index.html', balance=mock_balance, budget=mock_budget, progress=budget_progress)

@app.route('/transactions')
def transactions():
    return render_template('transactions.html', transactions=mock_transactions)

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if request.method == 'POST':
        goal_name = request.form['goal_name']
        target_amount = request.form['target_amount']
        deadline = request.form['deadline']
        mock_goals.append({"name": goal_name, "amount": target_amount, "deadline": deadline})
        return redirect(url_for('goals'))
    return render_template('goals.html', goals=mock_goals)

@app.route('/reports')
def reports():
    return render_template('reports.html')

if __name__ == '__main__':
    app.run(debug=True)
