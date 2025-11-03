import boto3
import json
from typing import List, Dict, Any

# ---------- CONFIGURATION ----------
REGION = "us-east-1"  # Change if needed
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
# ----------------------------------

# Initialize the Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

class AICategorizer:
    def categorize(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a single transaction by wrapping the batch method."""
        return self.batch_categorize([transaction_data])[0]

    def batch_categorize(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify a batch of transactions using Amazon Bedrock."""
        if not transactions:
            return []

        # Create a prompt for the model to process a batch of transactions
        prompt = f"""Based on the following JSON array of transaction data, please classify each transaction into one of these categories: Restaurant, Groceries, Transportation, Shopping, Utilities, Entertainment, or Other. 

        Return a JSON array where each object contains the original transaction and its corresponding category.

        <transactions>
        {json.dumps(transactions, indent=2)}
        </transactions>

        The JSON array of categories is:"""

        # Prepare the request body
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096, # Increased for larger batches
            "messages": [
                {
                    "role": "user",
                    "content": [{ "type": "text", "text": prompt}]
                }
            ]
        })

        print(f"🤖 Sending batch of {len(transactions)} transactions to Bedrock for classification...")

        try:
            # Invoke the model
            response = bedrock.invoke_model(
                body=body,
                modelId=MODEL_ID,
                accept="application/json",
                contentType="application/json",
            )

            # Parse the response
            response_body = json.loads(response.get("body").read())
            completion = response_body.get('content', [{}])[0].get('text', '').strip()

            # Extract the JSON array from the completion
            json_start = completion.find('[')
            json_end = completion.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                json_str = completion[json_start:json_end]
                categorized_transactions = json.loads(json_str)
                # Add a default confidence score
                for t in categorized_transactions:
                    t['confidence'] = 0.9
                return categorized_transactions
            else:
                print(f"Error: Could not find JSON array in Bedrock response: {completion}")
                return [{**t, 'category': 'Other', 'confidence': 0.3} for t in transactions]

        except Exception as e:
            print(f"Error during Bedrock invocation: {e}")
            return [{**t, 'category': 'Other', 'confidence': 0.3} for t in transactions]


class FraudDetector:
    def __init__(self, amount_threshold: float = 100000.0):
        self.amount_threshold = amount_threshold

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flags = []
        seen_merchants = set()
        for txn in transactions:
            amount = abs(float(txn.get('amount', 0)))
            merchant = (txn.get('merchant') or '').lower()
            if amount > self.amount_threshold:
                flags.append({'reason': 'Large amount', 'transaction': txn})
            if merchant and merchant not in seen_merchants:
                # First time seeing a new merchant in this batch
                flags.append({'reason': 'New merchant', 'transaction': txn})
                seen_merchants.add(merchant)
        return flags