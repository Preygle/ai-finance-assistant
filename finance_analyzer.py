import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pickle
import os
from typing import List, Dict, Any
import logging
from ai_service import AICategorizer
from fraud_engine import FraudEngine

logger = logging.getLogger(__name__)

class FinanceAnalyzerAI:
    """
    AI-powered finance analyzer that provides:
    - Transaction categorization
    - Fraud detection
    - Spending pattern analysis
    - Budget recommendations
    - Financial forecasting
    """
    
    def __init__(self):
        self.categorizer = AICategorizer()
        self.fraud_detector = None
        self.scaler = StandardScaler()
        self.model_path = 'instance/ai_models/'
        os.makedirs(self.model_path, exist_ok=True)
        
        # Load or initialize models
        self._load_or_initialize_models()
    
    def _load_or_initialize_models(self):
        """Load existing models or initialize new ones"""
        try:
            # Try to load existing models
            with open(os.path.join(self.model_path, 'fraud_detector.pkl'), 'rb') as f:
                self.fraud_detector = pickle.load(f)
            logger.info("Loaded existing AI models")
        except FileNotFoundError:
            # Initialize new models
            self._initialize_models()
            logger.info("Initialized new AI models")
    
    def _initialize_models(self):
        """Initialize new models with default training data"""
        self._train_fraud_detector()
    
    def _train_fraud_detector(self):
        """Train the fraud detection model"""
        # Generate synthetic normal transaction data
        np.random.seed(42)
        normal_amounts = np.random.normal(1000, 500, 1000)  # Normal spending patterns
        normal_amounts = np.abs(normal_amounts)  # Ensure positive amounts
        
        # Add some outliers for training
        outliers = np.random.normal(5000, 2000, 50)  # High-value transactions
        outliers = np.abs(outliers)
        
        # Combine data
        all_amounts = np.concatenate([normal_amounts, outliers])
        all_amounts = all_amounts.reshape(-1, 1)
        
        # Train Isolation Forest
        self.fraud_detector = IsolationForest(contamination=0.1, random_state=42)
        self.fraud_detector.fit(all_amounts)
        
        # Save model
        with open(os.path.join(self.model_path, 'fraud_detector.pkl'), 'wb') as f:
            pickle.dump(self.fraud_detector, f)
    
    def categorize_transaction(self, description: str, amount: float = None) -> Dict[str, Any]:
        """Categorize a transaction using AI"""
        try:
            transaction_data = {
                "description": description,
                "amount": amount
            }
            return self.categorizer.categorize(transaction_data)
        except Exception as e:
            logger.error(f"Error categorizing transaction: {e}")
            return {'category': 'Other', 'confidence': 0.3}
    
    def detect_fraud(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect potentially fraudulent transactions"""
        if not transactions:
            return []
        
        try:
            fraud_engine = FraudEngine(transactions)
            return fraud_engine.detect_fraud()
        except Exception as e:
            logger.error(f"Error in fraud detection: {e}")
            return []
    
    def _calculate_risk_score(self, amount: float, flags: List[str]) -> float:
        """Calculate risk score for a transaction"""
        score = 0.0
        
        # Amount-based scoring
        if amount > 100000:
            score += 0.4
        elif amount > 50000:
            score += 0.3
        elif amount > 20000:
            score += 0.2
        
        # Flag-based scoring
        for flag in flags:
            if 'Extremely high' in flag:
                score += 0.3
            elif 'Unusual amount' in flag:
                score += 0.2
            elif 'Large ATM' in flag:
                score += 0.1
        
        return min(score, 1.0)
    
    def analyze_spending_patterns(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze spending patterns and provide insights"""
        if not transactions:
            return {'insights': [], 'recommendations': []}
        
        df = pd.DataFrame(transactions)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        insights = []
        recommendations = []
        
        # Spending by category
        category_spending = df.groupby('category')['amount'].sum().abs()
        top_categories = category_spending.nlargest(5)
        
        insights.append(f"Top spending category: {top_categories.index[0]} (₹{top_categories.iloc[0]:,.2f})")
        
        # Monthly spending trend
        df['month'] = df['date'].dt.to_period('M')
        monthly_spending = df.groupby('month')['amount'].sum().abs()
        
        if len(monthly_spending) > 1:
            trend = monthly_spending.iloc[-1] - monthly_spending.iloc[-2]
            if trend > 0:
                insights.append(f"Spending increased by ₹{trend:,.2f} this month")
                recommendations.append("Consider reviewing your budget for next month")
            else:
                insights.append(f"Spending decreased by ₹{abs(trend):,.2f} this month")
        
        # Average transaction size
        avg_transaction = df['amount'].abs().mean()
        insights.append(f"Average transaction size: ₹{avg_transaction:,.2f}")
        
        # Spending frequency
        daily_transactions = df.groupby(df['date'].dt.date).size()
        avg_daily = daily_transactions.mean()
        insights.append(f"Average transactions per day: {avg_daily:.1f}")
        
        # Recommendations based on patterns
        if avg_transaction > 5000:
            recommendations.append("Consider breaking down large purchases into smaller ones")
        
        if avg_daily > 5:
            recommendations.append("High transaction frequency - consider consolidating purchases")
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'category_spending': category_spending.to_dict(),
            'monthly_trend': {str(k): v for k, v in monthly_spending.items()}
        }


    
    def generate_budget_recommendations(self, transactions: List[Dict[str, Any]], income: float = None) -> Dict[str, Any]:
        """Generate budget recommendations based on spending patterns"""
        if not transactions:
            return {'budgets': {}, 'recommendations': []}
        
        df = pd.DataFrame(transactions)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Calculate spending by category
        expenses = df[df['amount'] < 0]  # Negative amounts are expenses
        category_spending = expenses.groupby('category')['amount'].sum().abs()
        
        # Calculate total expenses
        total_expenses = category_spending.sum()
        
        # Generate budget recommendations
        budgets = {}
        recommendations = []
        
        # Standard budget allocation percentages
        budget_percentages = {
            'Housing': 0.30,
            'Groceries': 0.15,
            'Transportation': 0.10,
            'Dining': 0.10,
            'Entertainment': 0.05,
            'Healthcare': 0.05,
            'Shopping': 0.10,
            'Utilities': 0.05,
            'Savings': 0.10
        }
        
        if income:
            for category, percentage in budget_percentages.items():
                budgets[category] = income * percentage
        else:
            # Estimate income based on expenses (assume 30% savings rate)
            estimated_income = total_expenses / 0.7
            for category, percentage in budget_percentages.items():
                budgets[category] = estimated_income * percentage
        
        # Compare actual spending with recommended budgets
        for category, actual_spending in category_spending.items():
            if category in budgets:
                recommended = budgets[category]
                if actual_spending > recommended * 1.2:  # 20% over budget
                    recommendations.append(f"Consider reducing {category} spending (currently ₹{actual_spending:,.2f} vs recommended ₹{recommended:,.2f})")
                elif actual_spending < recommended * 0.8:  # 20% under budget
                    recommendations.append(f"Good job staying under budget for {category}!")
        
        return {
            'budgets': budgets,
            'recommendations': recommendations,
            'total_expenses': total_expenses,
            'estimated_income': income or (total_expenses / 0.7)
        }
    
    def retrain_models(self, new_data: pd.DataFrame):
        """Retrain models with new data"""
        try:
            if 'description' in new_data.columns and 'category' in new_data.columns:
                self._train_categorizer(new_data)
            
            # Retrain fraud detector with new transaction amounts
            amounts = new_data['amount'].abs().values.reshape(-1, 1)
            if len(amounts) > 10:  # Need sufficient data
                self._train_fraud_detector()
            
            logger.info("Models retrained successfully")
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
