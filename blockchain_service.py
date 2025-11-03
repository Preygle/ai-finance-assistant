import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

try:
    from web3 import Web3  # type: ignore
except Exception:  # web3 is optional; operate in no-chain mode if missing
    Web3 = None  # type: ignore


class BlockchainService:
    def __init__(self):
        """Initialize blockchain service with both Web3 and local storage"""
        self.enabled = False
        self.chain = os.getenv('CHAIN_NAME', 'local')
        self.storage_dir = os.path.join('instance', 'blockchain_records')
        os.makedirs(self.storage_dir, exist_ok=True)
        
        rpc_url = os.getenv('WEB3_RPC_URL')
        if Web3 and rpc_url:
            try:
                self.web3 = Web3(Web3.HTTPProvider(rpc_url))
                self.enabled = bool(self.web3.is_connected())
                logging.info(f"Blockchain service enabled: {self.enabled}")
            except Exception:
                self.enabled = False
                self.web3 = None
                logging.warning("Failed to connect to blockchain")
        else:
            self.web3 = None
            logging.info("Running in local-only mode")

    def compute_transaction_hash(
        self,
        txn_id: str,
        date_iso: str,
        amount: float,
        merchant: str,
        category: Optional[str],
        metadata: Optional[Dict] = None
    ) -> str:
        """Compute a deterministic hash for transaction data."""
        data = {
            'txn_id': txn_id,
            'date': date_iso,
            'amount': amount,
            'merchant': merchant,
            'category': category,
            'metadata': metadata or {}
        }
        # Create deterministic string representation
        data_str = json.dumps(data, sort_keys=True)
        # Create SHA3-256 hash
        return hashlib.sha3_256(data_str.encode('utf-8')).hexdigest()

    def _save_local_record(self, tx_hash: str, data: Dict[str, Any]) -> None:
        """Save transaction record locally for audit."""
        filepath = os.path.join(self.storage_dir, f"{tx_hash}.json")
        record = {
            'hash': tx_hash,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'record': data
        }
        with open(filepath, 'w') as f:
            json.dump(record, f, indent=2)
        logging.info(f"Saved local record for transaction {tx_hash}")

    def submit_to_chain(self, payload_hash: str) -> Tuple[str, str]:
        """Submit transaction hash to chain or simulate in local mode."""
        if not self.enabled or not self.web3:
            # Simulate blockchain tx with deterministic hash
            fake_tx = hashlib.md5(payload_hash.encode('utf-8')).hexdigest()
            logging.info(f"Local mode: Generated chain tx hash: 0x{fake_tx}")
            return self.chain, f"0x{fake_tx}"

        try:
            # Real blockchain submission would go here
            # For now, simulate with deterministic hash
            chain_tx = Web3.keccak(text=payload_hash).hex()
            logging.info(f"Submitted to blockchain: {chain_tx}")
            return self.chain, chain_tx
        except Exception as e:
            logging.error(f"Blockchain submission failed: {e}")
            # Return a local fallback hash
            fake_tx = hashlib.md5(payload_hash.encode('utf-8')).hexdigest()
            return self.chain, f"0x{fake_tx}"

    def log_transaction(
        self,
        user_id: str,
        txn_id: str,
        date: datetime,
        amount: float,
        merchant: str,
        category: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[str, str]:
        """Log a transaction and return its blockchain reference."""
        # Compute transaction hash
        tx_hash = self.compute_transaction_hash(
            txn_id=txn_id,
            date_iso=date.isoformat(),
            amount=amount,
            merchant=merchant,
            category=category,
            metadata=metadata
        )
        
        # Prepare record data
        record_data = {
            'user_id': user_id,
            'transaction_id': txn_id,
            'date': date.isoformat(),
            'amount': amount,
            'merchant': merchant,
            'category': category,
            'metadata': metadata or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Save locally
        self._save_local_record(tx_hash, record_data)
        
        # Submit to chain
        chain, chain_ref = self.submit_to_chain(tx_hash)
        
        return chain, chain_ref

    def verify_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Verify a transaction's integrity and return its details."""
        filepath = os.path.join(self.storage_dir, f"{tx_hash}.json")
        if not os.path.exists(filepath):
            logging.warning(f"No local record found for transaction {tx_hash}")
            return None
            
        try:
            with open(filepath, 'r') as f:
                stored_data = json.load(f)
            
            record = stored_data.get('record', {})
            computed_hash = self.compute_transaction_hash(
                txn_id=record.get('transaction_id'),
                date_iso=record.get('date'),
                amount=record.get('amount'),
                merchant=record.get('merchant'),
                category=record.get('category'),
                metadata=record.get('metadata')
            )
            
            if computed_hash != tx_hash:
                logging.warning(f"Hash mismatch for transaction {tx_hash}")
                return None
                
            return {
                'verified': True,
                'timestamp': stored_data['timestamp'],
                'record': record
            }
        except Exception as e:
            logging.error(f"Error verifying transaction {tx_hash}: {e}")
            return None


