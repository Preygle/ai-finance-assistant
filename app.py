from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timedelta
import logging
from forms import RegistrationForm, LoginForm, CSVUploadForm, CSVProcessForm
from extensions import db, migrate, csrf, login_manager, jwt
from flask_login import login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, JWTManager, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from plaid_service import PlaidService
from blockchain_service import BlockchainService
from ai_service import AICategorizer, FraudDetector
from finance_analyzer import FinanceAnalyzerAI
# Bedrock integration helper (generates AI-powered insights when configured)
from bedrock_integration import generate_insights_bedrock
from blockchain_logger import deploy_contract, log_transaction_to_chain, get_logged_events

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

def get_utc_now():
    """Get current UTC time as timezone-naive datetime"""
    return datetime.utcnow()

def ensure_naive_datetime(dt):
    """Ensure datetime is timezone-naive"""
    if dt is None:
        return None
    if isinstance(dt, str):
        # If stored as string, parse it
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is not None:
        # If timezone-aware, convert to naive
        dt = dt.replace(tzinfo=None)
    return dt

def create_app():
    """Create and configure an instance of the Flask application."""
    logging.debug("Starting create_app")
    app = Flask(__name__)

    # Load configuration from config.py
    app.config.from_object('config.Config')

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)

    # Configure login manager
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # JWT Error Handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return redirect(url_for('session_timeout'))

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return redirect(url_for('session_timeout'))

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return redirect(url_for('session_timeout'))

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return redirect(url_for('session_timeout'))

    def risk_level(score):
        if score is None:
            return 'ok'
        try:
            score = float(score)
            if score >= 7:
                return 'high'
            elif score >= 4:
                return 'medium'
            elif score > 0:
                return 'low'
            else:
                return 'ok'
        except (TypeError, ValueError):
            return 'ok'

    app.jinja_env.filters['risk_level'] = risk_level

    # Import models
    from models import User, Transaction, AIModelStorage, IntegrityProof, TransactionAIFiltered

    with app.app_context():
        logging.debug("Entering app context to create database tables")
        db.create_all()
        logging.debug("Finished creating database tables")

    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf())

    # Initialize services
    blockchain = BlockchainService()
    ai_categorizer = AICategorizer()
    fraud_detector = FraudDetector()
    finance_analyzer = FinanceAnalyzerAI()

    # Session timeout middleware
    @app.before_request
    def check_session_timeout():
        # Skip timeout check for login, register, and static files
        if request.endpoint in ['login', 'register', 'static'] or request.path.startswith('/static/'):
            return
        
        # Check if user is authenticated
        if current_user.is_authenticated:
            # Check if session has expired (30 minutes)
            if 'last_activity' in session:
                last_activity = ensure_naive_datetime(session['last_activity'])
                
                if get_utc_now() - last_activity > timedelta(minutes=30):
                    return redirect(url_for('session_timeout'))
            
            # Update last activity time (store as timezone-naive)
            session['last_activity'] = get_utc_now()

    # Authentication routes
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            flash('You are already registered and logged in.', 'info')
            return redirect(url_for('index'))
        form = RegistrationForm()
        if form.validate_on_submit():
            username = form.username.data
            email = form.email.data
            password = form.password.data

            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'error')
                return render_template('register.html', form=form)

            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'error')
                return render_template('register.html', form=form)

            user = User(username=username, email=email)
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            flash('You are already logged in.', 'info')
            return redirect(url_for('index'))
        
        # Check if redirected due to timeout
        if request.args.get('timeout') == '1':
            flash('⚠️ WARNING: You have been logged out due to inactivity! Your session expired after 30 minutes of no activity.', 'error')
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user, remember=form.remember.data)
                user.last_login = get_utc_now()
                db.session.commit()
                
                # Create JWT tokens (use default expiry from config)
                access_token = create_access_token(identity=user.id)
                refresh_token = create_refresh_token(identity=user.id)
                
                flash('Login successful!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'error')
        
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    @app.route('/session-timeout')
    def session_timeout():
        """Dedicated page for session timeout warning"""
        logout_user()
        session.clear()
        return render_template('session_timeout.html')

    @app.route('/refresh', methods=['POST'])
    @jwt_required(refresh=True)
    def refresh():
        current_user_id = get_jwt_identity()
        new_token = create_access_token(identity=current_user_id)
        return jsonify({'access_token': new_token})

    @app.route('/api/session/refresh', methods=['POST'])
    @login_required
    def refresh_session():
        """Refresh session activity timestamp"""
        # Store as timezone-naive datetime
        session['last_activity'] = get_utc_now()
        return jsonify({'success': True, 'message': 'Session refreshed'})

    # Main routes
    @app.route('/')
    def index():
        logging.debug("Accessing index route")
        if current_user.is_authenticated:
            logging.debug(f"User {current_user.username} is authenticated")
            return render_template('index.html', user=current_user)
        else:
            logging.debug("User is not authenticated")
            return render_template('index.html')

    @app.route('/upload')
    @login_required
    def upload():
        return render_template('upload.html', user=current_user)

    @app.route('/dashboard')
    @login_required
    def dashboard():
        # Get recent transactions for dashboard
        recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
            .order_by(Transaction.date.desc()).limit(10).all()
        
        # Calculate basic stats
        all_transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        total_income = sum(t.amount for t in all_transactions if t.amount > 0)
        total_expenses = abs(sum(t.amount for t in all_transactions if t.amount < 0))
        net_balance = total_income - total_expenses
        
        # Get AI insights
        transaction_data = [t.to_dict() for t in all_transactions]
        spending_analysis = finance_analyzer.analyze_spending_patterns(transaction_data)
        budget_recommendations = finance_analyzer.generate_budget_recommendations(transaction_data, total_income)
        
        return render_template('dashboard.html', 
                             user=current_user,
                             recent_transactions=recent_transactions,
                             total_income=total_income,
                             total_expenses=total_expenses,
                             net_balance=net_balance,
                             spending_analysis=spending_analysis,
                             budget_recommendations=budget_recommendations)

    @app.route('/analytics')
    @login_required
    def analytics():
        # Get date filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build query for transactions
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        # Apply date filters if provided
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Transaction.date >= start, Transaction.date <= end)
            except ValueError:
                flash('Invalid date format. Using all transactions.', 'warning')

        # Get transactions
        transactions = query.order_by(Transaction.date.desc()).all()
        
        # Initialize prev_transactions to None
        prev_transactions = None
        
        # Calculate current period stats
        total_income = sum(t.amount for t in transactions if t.amount > 0)
        total_expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
        net_savings = total_income - total_expenses
        
        # Calculate daily averages
        if transactions:
            date_range = (max(t.date for t in transactions) - min(t.date for t in transactions)).days + 1
            avg_daily_spend = total_expenses / date_range if date_range > 0 else 0
        else:
            avg_daily_spend = 0

        # Get previous period transactions for comparison
        if start_date and end_date:
            try:
                period_length = (datetime.strptime(end_date, '%Y-%m-%d').date() - 
                               datetime.strptime(start_date, '%Y-%m-%d').date()).days
                prev_end = datetime.strptime(start_date, '%Y-%m-%d').date() - timedelta(days=1)
                prev_start = prev_end - timedelta(days=period_length)
                
                prev_transactions = Transaction.query.filter_by(user_id=current_user.id)\
                    .filter(Transaction.date >= prev_start, Transaction.date <= prev_end).all()
                
                prev_income = sum(t.amount for t in prev_transactions if t.amount > 0)
                prev_expenses = abs(sum(t.amount for t in prev_transactions if t.amount < 0))
                
                income_change = ((total_income - prev_income) / prev_income * 100) if prev_income > 0 else 0
                expenses_change = ((total_expenses - prev_expenses) / prev_expenses * 100) if prev_expenses > 0 else 0
            except:
                income_change = 0
                expenses_change = 0
        else:
            income_change = 0
            expenses_change = 0

        # Calculate savings rate
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0

        # Prepare statistics
        stats = {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_savings': net_savings,
            'avg_daily_spend': avg_daily_spend,
            'income_change': income_change,
            'expenses_change': expenses_change,
            'savings_rate': savings_rate
        }

        # Prepare spending trends data
        spending_trends = {'labels': [], 'data': []}
        if transactions:
            df = pd.DataFrame([{
                'date': t.date,
                'amount': abs(t.amount) if t.amount < 0 else 0
            } for t in transactions])
            # Ensure date column is datetime
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.groupby('date')['amount'].sum().reset_index()
            df = df.sort_values('date')
            spending_trends['labels'] = df['date'].dt.strftime('%Y-%m-%d').tolist()
            spending_trends['data'] = df['amount'].tolist()

        # Prepare category distribution data
        category_distribution = {'labels': [], 'data': []}
        if transactions:
            df = pd.DataFrame([{
                'category': t.category or 'Uncategorized',
                'amount': abs(t.amount) if t.amount < 0 else 0
            } for t in transactions])
            df = df.groupby('category')['amount'].sum().reset_index()
            df = df.sort_values('amount', ascending=False)
            category_distribution['labels'] = df['category'].tolist()
            category_distribution['data'] = df['amount'].tolist()

        # Prepare monthly comparison data
        monthly_comparison = {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'current_year': [0] * 12,
            'previous_year': [0] * 12
        }
        
        if transactions:
            current_year = max(t.date.year for t in transactions)
            df = pd.DataFrame([{
                'year': t.date.year,
                'month': t.date.month - 1,  # 0-based index for months
                'amount': abs(t.amount) if t.amount < 0 else 0
            } for t in transactions if t.date.year in [current_year, current_year - 1]])
            
            current_year_data = df[df['year'] == current_year].groupby('month')['amount'].sum()
            prev_year_data = df[df['year'] == current_year - 1].groupby('month')['amount'].sum()
            
            for month, amount in current_year_data.items():
                monthly_comparison['current_year'][month] = amount
            for month, amount in prev_year_data.items():
                monthly_comparison['previous_year'][month] = amount

        # Prepare income vs expenses data
        income_expenses = {'labels': [], 'income': [], 'expenses': []}
        if transactions:
            # Create DataFrame with proper date handling
            df = pd.DataFrame([{
                'date': t.date,
                'income': t.amount if t.amount > 0 else 0,
                'expenses': abs(t.amount) if t.amount < 0 else 0
            } for t in transactions])
            
            # Convert to datetime and handle invalid dates
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])  # Remove invalid dates
            
            # Ensure daily aggregation
            df = df.groupby(df['date'].dt.date).agg({
                'income': 'sum',
                'expenses': 'sum'
            }).reset_index()
            
            # Sort by date and ensure continuous date range
            df = df.sort_values('date')
            date_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
            df = df.set_index('date').reindex(date_range, fill_value=0).reset_index()
            df = df.rename(columns={'index': 'date'})
            
            # Format dates for display
            income_expenses['labels'] = df['date'].dt.strftime('%b %d').tolist()
            income_expenses['income'] = df['income'].round(2).tolist()
            income_expenses['expenses'] = df['expenses'].round(2).tolist()
            
            income_expenses['labels'] = df['date'].dt.strftime('%Y-%m-%d').tolist()
            income_expenses['income'] = df['income'].tolist()
            income_expenses['expenses'] = df['expenses'].tolist()

        # Get AI insights (prefer Bedrock-generated JSON; fallback to local analyzer)
        transaction_data = [t.to_dict() for t in transactions]

        # Build a compact summary to send to the model (avoid sending huge raw lists)
        try:
            summary_lines = []
            summary_lines.append(f"Total transactions: {len(transaction_data)}")
            summary_lines.append(f"Total income: {total_income:.2f}")
            summary_lines.append(f"Total expenses: {total_expenses:.2f}")

            # top expense categories
            try:
                tdf = pd.DataFrame(transaction_data)
                if not tdf.empty and 'amount' in tdf.columns:
                    tdf['amount'] = pd.to_numeric(tdf['amount'], errors='coerce')
                    if 'category' in tdf.columns:
                        cat_sum = tdf[tdf['amount'] < 0].groupby('category')['amount'].sum().abs().sort_values(ascending=False).head(8)
                        summary_lines.append('Top expense categories:')
                        for cat, amt in cat_sum.items():
                            summary_lines.append(f"- {cat}: {amt:.2f}")

                    # largest transactions
                    top_txns = tdf.assign(abs_amount=tdf['amount'].abs()).sort_values('abs_amount', ascending=False).head(5)
                    summary_lines.append('Largest transactions:')
                    for _, r in top_txns.iterrows():
                        summary_lines.append(f"- {r.get('date', '')} | {r.get('merchant','')} | {float(r.get('amount',0)):.2f} | {r.get('category','')}")
            except Exception:
                # If summarization fails, continue with minimal summary
                pass

            prompt = (
                "You are an expert personal finance analyst. Based on the transaction summary below, produce a JSON object with three keys:\n"
                "1) patterns: an array of up to 5 concise observations about spending patterns,\n"
                "2) recommendations: an array of up to 5 actionable budget recommendations, and\n"
                "3) opportunities: an array of up to 5 specific savings or optimization opportunities.\n"
                "Return ONLY valid JSON with these keys (patterns, recommendations, opportunities). Do not include any additional text.\n\n"
                "Transaction summary:\n" + "\n".join(summary_lines)
            )

            bedrock_response = None
            try:
                # Try to generate a JSON response from Bedrock (requires AWS creds & Bedrock access)
                raw = generate_insights_bedrock(prompt, max_tokens=800)
                # Find the first { and last } to extract just the JSON part
                start = raw.find('{')
                end = raw.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = raw[start:end]
                    # Attempt to parse JSON from model output
                    import json as _json
                    try:
                        parsed = _json.loads(json_str)
                        if isinstance(parsed, dict):
                            patterns = parsed.get('patterns', [])
                            recommendations = parsed.get('recommendations', [])
                            opportunities = parsed.get('opportunities', [])
                            bedrock_response = True
                        else:
                            bedrock_response = False
                    except Exception:
                        # If model didn't return JSON, mark failure and fall back
                        bedrock_response = False
                else:
                    bedrock_response = False
            except Exception as e:
                # Bedrock call failed (network, creds, etc.) — fallback to local analyzer
                bedrock_response = False

            if not bedrock_response:
                # Local fallback
                patterns = finance_analyzer.analyze_spending_patterns(transaction_data)
                recommendations = finance_analyzer.generate_budget_recommendations(transaction_data, total_income)
                opportunities = [
                    "Potential savings in dining category - Consider meal planning",
                    "Recurring subscriptions optimization opportunity",
                    "Energy bill savings through smart home devices",
                    "Cashback opportunities on current spending patterns",
                    "Bulk purchase opportunities for frequent items"
                ]

        except Exception as e:
            # If anything in the AI pipeline fails, fallback to safer defaults
            logging.error(f"AI insights generation failed: {e}", exc_info=True)
            transaction_data = [t.to_dict() for t in transactions]
            patterns = finance_analyzer.analyze_spending_patterns(transaction_data)
            recommendations = finance_analyzer.generate_budget_recommendations(transaction_data, total_income)
            opportunities = [
                "Potential savings in dining category - Consider meal planning",
                "Recurring subscriptions optimization opportunity",
                "Energy bill savings through smart home devices",
                "Cashback opportunities on current spending patterns",
                "Bulk purchase opportunities for frequent items"
            ]

        # Calculate financial health score (simplified version)
        try:
            savings_score = min(100, (savings_rate / 20) * 100)  # Aim for 20% savings rate
            expense_stability_score = min(100, (100 - expenses_change) if expenses_change > 0 else 100)
            income_growth_score = min(100, (income_change + 100) if income_change > -100 else 0)
            
            health_score = int((savings_score + expense_stability_score + income_growth_score) / 3)
            
            if health_score >= 80:
                health_description = "Excellent financial health! Keep up the great work!"
            elif health_score >= 60:
                health_description = "Good financial health. Some room for improvement."
            elif health_score >= 40:
                health_description = "Fair financial health. Consider implementing the recommendations."
            else:
                health_description = "Needs attention. Focus on building savings and reducing expenses."
        except:
            health_score = 0
            health_description = "Insufficient data to calculate health score."

        ai_insights = {
            'patterns': list(patterns.values())[:5] if isinstance(patterns, dict)
                       else (patterns[:5] if isinstance(patterns, list) else []),  # Top 5 patterns
            'recommendations': list(recommendations.values())[:5] if isinstance(recommendations, dict)
                             else (recommendations[:5] if isinstance(recommendations, list) else []),  # Top 5 recommendations
            'opportunities': opportunities if 'opportunities' in locals() else [
                "Potential savings in dining category - Consider meal planning",
                "Recurring subscriptions optimization opportunity",
                "Energy bill savings through smart home devices",
                "Cashback opportunities on current spending patterns",
                "Bulk purchase opportunities for frequent items"
            ],
            'health_score': health_score,
            'health_description': health_description
        }

        # Prepare detailed metrics
        detailed_metrics = []
        if transactions:
            # Calculate current period metrics
            current_metrics = {
                'Average Transaction Size': sum(abs(t.amount) for t in transactions) / len(transactions) if transactions else 0,
                'Monthly Savings Rate': savings_rate,
                'Discretionary Spending': sum(abs(t.amount) for t in transactions if t.category in ['Entertainment', 'Dining', 'Shopping']),
                'Essential Expenses': sum(abs(t.amount) for t in transactions if t.category in ['Utilities', 'Rent', 'Groceries'])
            }
            
            # Calculate previous period metrics if available
            if prev_transactions:
                prev_metrics = {
                    'Average Transaction Size': sum(abs(t.amount) for t in prev_transactions) / len(prev_transactions) if prev_transactions else 0,
                    'Monthly Savings Rate': (prev_income - prev_expenses) / prev_income * 100 if prev_income > 0 else 0,
                    'Discretionary Spending': sum(abs(t.amount) for t in prev_transactions if t.category in ['Entertainment', 'Dining', 'Shopping']),
                    'Essential Expenses': sum(abs(t.amount) for t in prev_transactions if t.category in ['Utilities', 'Rent', 'Groceries'])
                }
                
                # Calculate metrics with changes
                for name, current in current_metrics.items():
                    previous = prev_metrics[name]
                    change = ((current - previous) / previous * 100) if previous > 0 else 0
                    detailed_metrics.append({
                        'name': name,
                        'current': current,
                        'previous': previous,
                        'change': change
                    })
            else:
                # If no previous data, show current values with 0 for previous and change
                for name, current in current_metrics.items():
                    detailed_metrics.append({
                        'name': name,
                        'current': current,
                        'previous': 0,
                        'change': 0
                    })

        return render_template('analytics.html',
                            user=current_user,
                            stats=stats,
                            spending_trends=spending_trends,
                            category_distribution=category_distribution,
                            monthly_comparison=monthly_comparison,
                            income_expenses=income_expenses,
                            ai_insights=ai_insights,
                            detailed_metrics=detailed_metrics)

    @app.route('/transactions')
    @login_required
    def transactions():
        form = CSVUploadForm()
        return render_template('transactions.html', user=current_user, form=form)

    @app.route('/upload_csv', methods=['POST'])
    @login_required
    def upload_csv():
        form = CSVUploadForm()
        if form.validate_on_submit():
            try:
                # Save the file to a temporary location
                temp_dir = os.path.join(app.instance_path, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                temp_filepath = os.path.join(temp_dir, form.csv_file.data.filename)
                form.csv_file.data.save(temp_filepath)

                # Read the CSV for preview
                df = pd.read_csv(temp_filepath)
                preview_data = df.head().to_dict(orient='records')
                headers = df.columns.tolist()

                # Store the temp filepath in the session
                session['csv_filepath'] = temp_filepath

                process_form = CSVProcessForm()
                return render_template('preview_csv.html', headers=headers, preview_data=preview_data, form=process_form)

            except Exception as e:
                flash(f'Error processing CSV file: {e}', 'error')
                return redirect(url_for('transactions'))
        else:
            # Flash form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'error')
            return redirect(url_for('transactions'))

    @app.route('/process_csv', methods=['POST'])
    @login_required
    def process_csv():
        temp_filepath = session.get('csv_filepath')
        if not temp_filepath or not os.path.exists(temp_filepath):
            flash('No CSV file to process.', 'error')
            return redirect(url_for('transactions'))

        try:
            df = pd.read_csv(temp_filepath)
            headers = df.columns.tolist()
            choices = [(str(i), header) for i, header in enumerate(headers)]
        except Exception as e:
            flash(f'Could not read CSV headers: {e}', 'error')
            return redirect(url_for('transactions'))

        form = CSVProcessForm()
        form.date_column.choices = choices
        form.merchant_column.choices = choices
        form.amount_column.choices = choices
        form.category_column.choices = [('', 'Select category column (optional)')] + choices

        if form.validate_on_submit():
            try:
                # Get column mappings from form
                date_column = int(form.date_column.data)
                merchant_column = int(form.merchant_column.data)
                amount_column = int(form.amount_column.data)
                category_column = form.category_column.data
                currency = form.currency.data
                
                # Read CSV file
                df = pd.read_csv(temp_filepath)
                
                # Currency conversion rates (simplified - in production use real API)
                currency_rates = {
                    'INR': 1.0,
                    'USD': 83.0,
                    'EUR': 90.0,
                    'GBP': 105.0
                }
                
                conversion_rate = currency_rates.get(currency, 1.0)
                
                # Process each row
                transactions_added = 0
                proofs_logged = 0
                processed_txns = []
                for index, row in df.iterrows():
                    try:
                        # Parse date
                        date_str = str(row.iloc[date_column])
                        transaction_date = pd.to_datetime(date_str).date()
                        
                        # Get merchant name
                        merchant = str(row.iloc[merchant_column])
                        
                        # Get amount and convert to INR
                        amount = float(row.iloc[amount_column]) * conversion_rate
                        
                        # Get category if specified
                        category = None
                        if category_column and category_column != '':
                            category = str(row.iloc[int(category_column)])
                        
                        # Compute integrity hash and optionally store
                        txn_id = f"csv:{current_user.id}:{index}"
                        payload_hash = blockchain.compute_transaction_hash(
                            txn_id=txn_id,
                            date_iso=transaction_date.isoformat(),
                            amount=amount,
                            merchant=merchant,
                            category=category,
                        )
                        chain, chain_tx = blockchain.submit_to_chain(payload_hash)
                        db.session.add(
                            IntegrityProof(
                                user_id=current_user.id,
                                txn_hash=payload_hash,
                                chain_tx_hash=chain_tx,
                                chain=chain,
                            )
                        )
                        proofs_logged += 1

                        # Respect privacy mode (do not persist raw data if enabled)
                        if not app.config.get('PRIVACY_MODE', False):
                            transaction = Transaction(
                                user_id=current_user.id,
                                date=transaction_date,
                                merchant=merchant,
                                amount=amount,
                                category=category,
                                source='csv'
                            )
                            db.session.add(transaction)
                            transactions_added += 1
                        
                        processed_txns.append({
                            'date': transaction_date.isoformat(),
                            'merchant': merchant,
                            'amount': amount,
                            'category': category,
                            'description': merchant,
                        })
                        
                    except Exception as e:
                        logging.warning(f"Error processing row {index}: {e}")
                        continue
                
                db.session.commit()
                
                # Perform AI & fraud analysis
                categorized_txns = ai_categorizer.batch_categorize(processed_txns)
                fraud_results = fraud_detector.detect(categorized_txns)
                
                # Store fraud detection results
                if fraud_results:
                    session['fraud_flags'] = fraud_results
                    warning_msg = f' WARNING: Found {len(fraud_results)} suspicious transactions! Check the fraud report for details.'
                else:
                    session['fraud_flags'] = []
                    warning_msg = ''
                
                if app.config.get('PRIVACY_MODE', False):
                    flash(f'Successfully logged {proofs_logged} transaction proofs to blockchain.{warning_msg}', 'success')
                else:
                    flash(f'Successfully processed {transactions_added} transactions and logged {proofs_logged} proofs.{warning_msg}', 'success')

            except Exception as e:
                db.session.rollback()
                flash(f'Error processing CSV file: {e}', 'error')
                logging.error(f"CSV processing error: {e}")
            
            finally:
                # Clean up the temporary file and session variable
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                session.pop('csv_filepath', None)
        else:
            # Flash form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'error')

        return redirect(url_for('transactions'))

    # Analytics API endpoints
    @app.route('/api/analytics/spending-patterns')
    @login_required
    def api_spending_patterns():
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        transaction_data = [t.to_dict() for t in transactions]
        # Try Bedrock first (return JSON {"patterns": [...]})
        try:
            summary = f"Total transactions: {len(transaction_data)}\nTotal income: {sum(t['amount'] for t in transaction_data if t.get('amount')):.2f}\nTotal expenses: {abs(sum(t['amount'] for t in transaction_data if t.get('amount') and t['amount']<0)):.2f}"
            prompt = (
                "You are an expert personal finance analyst. Based on the transaction summary below, return a JSON object with a single key 'patterns' which is an array of up to 8 concise spending pattern observations. Return ONLY valid JSON.\n\n"
                "Transaction summary:\n" + summary
            )
            raw = generate_insights_bedrock(prompt, max_tokens=400)
            import json as _json
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict) and 'patterns' in parsed:
                    return jsonify(parsed)
            except Exception:
                pass
        except Exception:
            pass

        # Fallback
        analysis = finance_analyzer.analyze_spending_patterns(transaction_data)
        return jsonify({'patterns': analysis})
    
    @app.route('/api/analytics/budget-recommendations')
    @login_required
    def api_budget_recommendations():
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        transaction_data = [t.to_dict() for t in transactions]
        total_income = sum(t.amount for t in transactions if t.amount > 0)
        # Try Bedrock first (return JSON {"recommendations": [...]})
        try:
            summary = f"Total transactions: {len(transaction_data)}\nTotal income: {total_income:.2f}\nTotal expenses: {abs(sum(t['amount'] for t in transaction_data if t.get('amount') and t['amount']<0)):.2f}"
            prompt = (
                "You are an expert personal finance advisor. Based on the transaction summary below, return a JSON object with a single key 'recommendations' which is an array of up to 8 actionable budget recommendations, prioritized. Return ONLY valid JSON.\n\n"
                "Transaction summary:\n" + summary
            )
            raw = generate_insights_bedrock(prompt, max_tokens=600)
            import json as _json
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict) and 'recommendations' in parsed:
                    return jsonify(parsed)
            except Exception:
                pass
        except Exception:
            pass

        # Fallback
        recommendations = finance_analyzer.generate_budget_recommendations(transaction_data, total_income)
        return jsonify({'recommendations': recommendations})
    
    @app.route('/api/fraud-detection')
    @login_required
    def api_fraud_detection():
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        transaction_data = [t.to_dict() for t in transactions]
        fraud_flags = finance_analyzer.detect_fraud(transaction_data)
        return jsonify({'fraud_flags': fraud_flags})

    @app.route('/fraud-report')
    @login_required
    def fraud_report():
        logging.info(f"Generating fraud report for user {current_user.id}")
        
        # Get date filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build query for transactions - start with all user transactions
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        # Apply date filters only if both dates are provided
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Transaction.date >= start, Transaction.date <= end)
                logging.info(f"Applying date filter: {start} to {end}")
            except ValueError as e:
                flash('Invalid date format. Using all transactions.', 'warning')
                logging.warning(f"Invalid date format: {e}")
        
        # Order by date descending
        transactions = query.order_by(Transaction.date.desc()).all()
        logging.info(f"Found {len(transactions)} transactions")
        
        # Convert transactions to dictionary format for fraud engine
        # Fraud engine expects: date (ISO string or datetime), merchant, amount, category, description
        transaction_data = []
        for t in transactions:
            try:
                # Ensure date is in ISO format string that pandas can parse
                date_str = t.date.isoformat() if hasattr(t.date, 'isoformat') else str(t.date)
                
                # Create transaction dict with all required fields
                tx_dict = {
                    'date': date_str,
                    'merchant': t.merchant or 'Unknown',
                    'amount': float(t.amount),
                    'category': t.category or 'Uncategorized',
                    'description': t.description or t.merchant or 'No description',
                    'id': t.id,
                    'source': t.source,
                    'created_at': t.created_at.isoformat() if t.created_at else None
                }
                transaction_data.append(tx_dict)
            except Exception as e:
                logging.error(f"Error converting transaction {t.id} to dict: {e}")
                continue
        
        # Analyze all transactions using FraudEngine
        try:
            from fraud_engine import FraudEngine
            fraud_engine = FraudEngine(transaction_data)
            fraud_flags = fraud_engine.detect_fraud()
            logging.info(f"Generated {len(fraud_flags)} fraud analysis entries")
            
            # Ensure fraud_flags is a list (handle None case)
            if fraud_flags is None:
                fraud_flags = []
                logging.warning("Fraud detection returned None, using empty list")
        except Exception as e:
            logging.error(f"Error in fraud detection: {e}", exc_info=True)
            fraud_flags = []
            flash(f'Error during fraud analysis: {e}', 'error')
        
        # Ensure we have an entry for every transaction
        if len(fraud_flags) != len(transaction_data):
            logging.warning(f"Mismatch: {len(transaction_data)} transactions but {len(fraud_flags)} fraud flags")
            # Create default entries for missing transactions
            transaction_ids_in_flags = {f.get('transaction', {}).get('id') for f in fraud_flags if f.get('transaction', {}).get('id')}
            for tx in transaction_data:
                if tx.get('id') not in transaction_ids_in_flags:
                    fraud_flags.append({
                        'transaction': tx,
                        'triggered_rules': [],
                        'risk_score': 0.0
                    })
        
        # Calculate summary stats
        stats = {
            'total_transactions': len(transactions),
            'suspicious_transactions': len([f for f in fraud_flags if f['risk_score'] > 0]),
        }
        
        if transactions:
            stats['date_range'] = {
                'start': min(t.date for t in transactions).strftime('%Y-%m-%d'),
                'end': max(t.date for t in transactions).strftime('%Y-%m-%d')
            }
            
        # Calculate detailed statistics
        high_risk = [f for f in fraud_flags if f.get('risk_score', 0) >= 7]
        medium_risk = [f for f in fraud_flags if 4 <= f.get('risk_score', 0) < 7]
        low_risk = [f for f in fraud_flags if 0 < f.get('risk_score', 0) < 4]
        no_risk = [f for f in fraud_flags if f.get('risk_score', 0) == 0]
        
        stats = {
            'total_transactions': len(transactions),
            'suspicious_transactions': len([f for f in fraud_flags if f.get('risk_score', 0) > 0]),
            'high_risk_count': len(high_risk),
            'medium_risk_count': len(medium_risk),
            'low_risk_count': len(low_risk),
            'no_risk_count': len(no_risk),
            'date_range': {
                'start': min(t.date for t in transactions).strftime('%Y-%m-%d') if transactions else None,
                'end': max(t.date for t in transactions).strftime('%Y-%m-%d') if transactions else None
            } if transactions else None
        }
        
        logging.info(f"Stats: {stats}")
        
        return render_template('fraud_report.html', 
                             fraud_flags=fraud_flags,
                             stats=stats,
                             transactions=transactions)
    
    @app.route('/api/ai/categorize', methods=['POST'])
    @login_required
    def api_categorize_transaction():
        data = request.get_json()
        description = data.get('description', '')
        amount = data.get('amount', 0)
        
        result = finance_analyzer.categorize_transaction(description, amount)
        return jsonify(result)

    @app.route('/plaid_connect')
    @login_required
    def plaid_connect():
        try:
            # Simulate getting transactions from Plaid by reading the fraudulent_transactions.csv file
            df = pd.read_csv('fraudulent_transactions.csv')
            processed_txns = []
            
            for index, row in df.iterrows():
                try:
                    try:
                        date = datetime.strptime(row['Date'], '%Y-%m-%dT%H:%M:%S').date()
                    except ValueError:
                        date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
                    
                    transaction = Transaction(
                        user_id=current_user.id,
                        date=date,
                        merchant=row['Merchant'],
                        amount=row['Amount'],
                        category=row['Category'],
                        description=row['Description'],
                        source='plaid',
                        plaid_transaction_id=f"plaid_{row['Merchant'].replace(' ', '_').lower()}_{row['Date']}"
                    )
                    db.session.add(transaction)
                    
                    processed_txns.append({
                        'date': date.isoformat(),
                        'merchant': row['Merchant'],
                        'amount': float(row['Amount']),
                        'category': row['Category'],
                        'description': row['Description']
                    })
                    
                except Exception as e:
                    logging.error(f"Error processing transaction {index}: {e}")
                    continue
            
            db.session.commit()
            
            # Perform fraud detection
            fraud_flags = finance_analyzer.detect_fraud(processed_txns)
            if fraud_flags:
                session['fraud_flags'] = fraud_flags
                flash(f'Successfully imported transactions. WARNING: Found {len(fraud_flags)} suspicious transactions! Check the fraud report for details.', 'warning')
            else:
                session['fraud_flags'] = []
                flash('Successfully connected to bank and imported transactions!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error connecting to bank: {e}', 'error')
            logging.error(f"Plaid connection error: {e}")
        
        return redirect(url_for('transactions'))

    # API endpoints for transactions
    @app.route('/api/transactions')
    @login_required
    def api_get_transactions():
        source_filter = request.args.get('source', 'all')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build query
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        if source_filter != 'all':
            query = query.filter_by(source=source_filter)
        
        if date_from:
            query = query.filter(Transaction.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        
        if date_to:
            query = query.filter(Transaction.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        
        transactions = query.order_by(Transaction.date.desc()).all()
        
        # Calculate summary
        total_income = sum(t.amount for t in transactions if t.amount > 0)
        total_expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
        net_balance = total_income - total_expenses
        
        return jsonify({
            'transactions': [t.to_dict() for t in transactions],
            'summary': {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_balance': net_balance
            }
        })

    @app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
    @login_required
    def api_delete_transaction(transaction_id):
        transaction = Transaction.query.filter_by(
            id=transaction_id, 
            user_id=current_user.id
        ).first()
        
        if not transaction:
            return jsonify({'success': False, 'message': 'Transaction not found'}), 404
        
        try:
            db.session.delete(transaction)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Transaction deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/delete_transactions', methods=['POST'])
    @login_required
    def delete_transactions():
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        confirm_delete = request.form.get('confirm_delete')

        if not confirm_delete:
            flash('You must confirm the deletion.', 'error')
            return redirect(url_for('transactions'))

        try:
            query = Transaction.query.filter_by(user_id=current_user.id)

            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(Transaction.date >= start_date)

            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(Transaction.date <= end_date)

            # Get the number of transactions to be deleted before deleting them
            count = query.count()

            # Delete the transactions
            query.delete(synchronize_session=False)
            db.session.commit()

            if start_date_str and end_date_str:
                flash(f'Successfully deleted {count} transactions between {start_date_str} and {end_date_str}.', 'success')
            elif start_date_str:
                flash(f'Successfully deleted {count} transactions from {start_date_str} onwards.', 'success')
            elif end_date_str:
                flash(f'Successfully deleted {count} transactions up to {end_date_str}.', 'success')
            else:
                flash(f'Successfully deleted all {count} transactions.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting transactions: {e}', 'error')
            logging.error(f"Transaction deletion error: {e}")

        return redirect(url_for('transactions'))

    @app.route('/log_to_blockchain', methods=['POST'])
    @login_required
    def log_to_blockchain():
        try:
            # Deploy contract if not already deployed
            deploy_contract()
            
            # Fetch latest transactions from DB for the current user
            transactions = Transaction.query.filter_by(user_id=current_user.id).all()
            
            logged_count = 0
            for txn in transactions:
                txn_data = {
                    'merchant': txn.merchant,
                    'amount': txn.amount,
                    'category': txn.category or 'Uncategorized'
                }
                if log_transaction_to_chain(txn_data):
                    logged_count += 1
            
            return jsonify({"logged": logged_count, "success": True})
        except Exception as e:
            logging.error(f"Error logging to blockchain: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/blockchain_logs', methods=['GET'])
    @login_required
    def blockchain_logs():
        try:
            logs = get_logged_events()
            return render_template('blockchain_explorer.html', logs=logs)
        except Exception as e:
            logging.error(f"Error fetching blockchain logs: {e}", exc_info=True)
            flash(f"Could not fetch blockchain logs: {e}", "error")
            return render_template('blockchain_explorer.html', logs=[])

    logging.debug("create_app finished")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)