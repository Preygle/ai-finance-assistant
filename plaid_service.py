import os
import plaid
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.accounts_get_request import AccountsGetRequest
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class PlaidService:
    def __init__(self):
        # Plaid configuration
        self.client_id = os.getenv('PLAID_CLIENT_ID', 'your_client_id')
        self.secret = os.getenv('PLAID_SECRET', 'your_secret')
        self.environment = os.getenv('PLAID_ENV', 'sandbox')
        
        # Configure Plaid client
        configuration = plaid.Configuration(
            host=plaid.Environment.sandbox if self.environment == 'sandbox' else plaid.Environment.development,
            api_key={
                'clientId': self.client_id,
                'secret': self.secret,
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
    
    def get_access_token(self, public_token):
        """Exchange public token for access token"""
        try:
            request = {
                'public_token': public_token,
            }
            response = self.client.item_public_token_exchange(request)
            return response['access_token']
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None
    
    def get_accounts(self, access_token):
        """Get user's accounts"""
        try:
            request = AccountsGetRequest(access_token=access_token)
            response = self.client.accounts_get(request)
            return response['accounts']
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return []
    
    def get_transactions(self, access_token, start_date=None, end_date=None):
        """Get transactions for the specified date range"""
        try:
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).date()
            if not end_date:
                end_date = datetime.now().date()
            
            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
                options=TransactionsGetRequestOptions(
                    count=500,
                    offset=0
                )
            )
            response = self.client.transactions_get(request)
            return response['transactions']
        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            return []
    
    def format_transaction_for_storage(self, transaction, account_name):
        """Format Plaid transaction for our database"""
        # Convert amount to INR (assuming Plaid returns in USD, convert to INR)
        # In production, you'd want to use real exchange rates
        usd_to_inr_rate = 83.0  # Approximate rate, should be fetched from API
        amount_inr = abs(transaction['amount']) * usd_to_inr_rate
        
        # Determine if it's a debit or credit
        if transaction['amount'] < 0:
            amount_inr = -amount_inr  # Negative for debits
        
        return {
            'date': datetime.strptime(transaction['date'], '%Y-%m-%d').date(),
            'merchant': transaction.get('merchant_name', transaction.get('name', 'Unknown')),
            'amount': amount_inr,
            'category': ', '.join(transaction.get('category', ['Other'])),
            'description': transaction.get('name', ''),
            'source': 'plaid',
            'plaid_transaction_id': transaction['transaction_id']
        }

