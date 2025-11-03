import unittest
import os
import json
import shutil
from datetime import datetime, timezone
from blockchain_service import BlockchainService
from models import Transaction, User, IntegrityProof

class TestBlockchainService(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.test_storage_dir = os.path.join('instance', 'test_blockchain_records')
        # Clean up any existing test directory
        if os.path.exists(self.test_storage_dir):
            shutil.rmtree(self.test_storage_dir)
        
        self.service = BlockchainService()
        # Override storage directory for tests
        self.service.storage_dir = self.test_storage_dir
        os.makedirs(self.test_storage_dir, exist_ok=True)

    def tearDown(self):
        """Clean up after each test"""
        if os.path.exists(self.test_storage_dir):
            shutil.rmtree(self.test_storage_dir)

    def test_compute_transaction_hash(self):
        """Test transaction hash computation is deterministic"""
        test_data = {
            'txn_id': '123',
            'date_iso': '2024-01-01T12:00:00',
            'amount': 1000.0,
            'merchant': 'Test Store',
            'category': 'Shopping'
        }
        
        # Compute hash twice with same data
        hash1 = self.service.compute_transaction_hash(**test_data)
        hash2 = self.service.compute_transaction_hash(**test_data)
        
        # Verify hashes are same and in correct format
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA3-256 produces 64 char hex string

    def test_local_record_storage(self):
        """Test local storage of transaction records"""
        test_txn = {
            'txn_id': '456',
            'date': datetime.now(timezone.utc),
            'amount': 500.0,
            'merchant': 'Local Shop',
            'category': 'Food'
        }
        
        # Log transaction
        chain, chain_ref = self.service.log_transaction(
            user_id='test_user',
            **test_txn
        )
        
        # Compute expected hash
        test_txn['date_iso'] = test_txn['date'].isoformat()
        tx_hash = self.service.compute_transaction_hash(
            txn_id=test_txn['txn_id'],
            date_iso=test_txn['date_iso'],
            amount=test_txn['amount'],
            merchant=test_txn['merchant'],
            category=test_txn['category']
        )
        
        # Verify file exists
        file_path = os.path.join(self.test_storage_dir, f"{tx_hash}.json")
        self.assertTrue(os.path.exists(file_path))
        
        # Verify file content
        with open(file_path, 'r') as f:
            stored_data = json.load(f)
            self.assertEqual(stored_data['hash'], tx_hash)
            self.assertEqual(stored_data['record']['user_id'], 'test_user')
            self.assertEqual(stored_data['record']['transaction_id'], test_txn['txn_id'])
            self.assertEqual(stored_data['record']['amount'], test_txn['amount'])

    def test_transaction_verification(self):
        """Test transaction verification functionality"""
        # Create and log a transaction
        test_txn = {
            'txn_id': '789',
            'date': datetime.now(timezone.utc),
            'amount': 750.0,
            'merchant': 'Test Mart',
            'category': 'Groceries'
        }
        
        # Log transaction
        chain, chain_ref = self.service.log_transaction(
            user_id='test_user',
            **test_txn
        )
        
        # Compute hash
        test_txn['date_iso'] = test_txn['date'].isoformat()
        tx_hash = self.service.compute_transaction_hash(
            txn_id=test_txn['txn_id'],
            date_iso=test_txn['date_iso'],
            amount=test_txn['amount'],
            merchant=test_txn['merchant'],
            category=test_txn['category']
        )
        
        # Verify transaction
        verification_result = self.service.verify_transaction(tx_hash)
        
        # Check verification result
        self.assertIsNotNone(verification_result)
        self.assertTrue(verification_result['verified'])
        self.assertEqual(verification_result['record']['transaction_id'], test_txn['txn_id'])
        self.assertEqual(verification_result['record']['amount'], test_txn['amount'])

    def test_nonexistent_transaction(self):
        """Test verification of non-existent transaction"""
        result = self.service.verify_transaction('nonexistent_hash')
        self.assertIsNone(result)

    def test_submit_to_chain(self):
        """Test blockchain submission simulation"""
        test_hash = 'test_payload_hash'
        
        # Submit to chain
        chain, chain_ref = self.service.submit_to_chain(test_hash)
        
        # Verify we got expected response format
        self.assertIsNotNone(chain)
        self.assertTrue(isinstance(chain_ref, str))
        self.assertTrue(chain_ref.startswith('0x'))

if __name__ == '__main__':
    unittest.main()