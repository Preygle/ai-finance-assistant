
import json
import os
from web3 import Web3
from solcx import compile_source, install_solc
import hashlib

# --- Configuration ---
GANACHE_URL = "http://127.0.0.1:7545"
CONTRACT_FILE = "TransactionLogger.sol"
DEPLOYED_FILE = "deployed.json"

# --- Web3 Setup ---
w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
w3.eth.default_account = w3.eth.accounts[0]


def _compile_contract():
    """Compiles the Solidity contract."""
    install_solc(version='0.8.0')
    with open(CONTRACT_FILE, 'r') as f:
        source = f.read()
    compiled_sol = compile_source(source, output_values=['abi', 'bin'])
    contract_id, contract_interface = compiled_sol.popitem()
    return contract_interface['abi'], contract_interface['bin']


def deploy_contract():
    """
    Deploys the smart contract to the local Ganache instance if not already deployed.
    Saves the ABI and address to a JSON file.
    """
    if os.path.exists(DEPLOYED_FILE):
        with open(DEPLOYED_FILE, 'r') as f:
            return json.load(f)

    abi, bytecode = _compile_contract()

    # Deploy contract
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact()
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress

    # Save deployment info
    deployment_data = {
        "abi": abi,
        "address": contract_address
    }
    with open(DEPLOYED_FILE, 'w') as f:
        json.dump(deployment_data, f)

    return deployment_data


def get_contract():
    """Gets the deployed contract instance."""
    if not os.path.exists(DEPLOYED_FILE):
        raise FileNotFoundError(
            "Contract not deployed. Run deploy_contract() first.")

    with open(DEPLOYED_FILE, 'r') as f:
        deployment_data = json.load(f)

    contract = w3.eth.contract(
        address=deployment_data['address'],
        abi=deployment_data['abi']
    )
    return contract


def log_transaction_to_chain(transaction):
    """
    Hashes a transaction and logs it to the blockchain.

    Args:
        transaction (dict): A dictionary representing the transaction.
                            Example: {'merchant': 'Test',
                                'amount': 100, 'category': 'Test'}
    """
    contract = get_contract()

    # Create a stable hash
    txn_string = json.dumps(transaction, sort_keys=True)
    txn_hash = hashlib.sha256(txn_string.encode()).hexdigest()

    try:
        tx_hash = contract.functions.logTransaction(
            transaction['merchant'],
            int(transaction['amount']),
            transaction['category'],
            txn_hash
        ).transact()
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return txn_hash, tx_hash
    except Exception as e:
                print(f"Error logging transaction to blockchain: {e}")
                return None, None

# --- Initial Deployment ---
if __name__ == "__main__":
    print("Deploying contract...")
    deployment_info = deploy_contract()
    print(f"Contract deployed at address: {deployment_info['address']}")
