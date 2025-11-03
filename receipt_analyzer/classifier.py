import boto3
import json

# ---------- CONFIGURATION ----------
REGION = "us-east-1"  # Change if needed
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
# ----------------------------------

# Initialize the Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

def classify_transaction(transaction_data):
    """Classify a transaction into a category using Amazon Bedrock."""

    # Create a prompt for the model
    prompt = f"""Based on the following JSON data from a receipt, classify this transaction into one of these categories: Restaurant, Groceries, Transportation, Shopping, Utilities, Entertainment, or Other.
    Your response MUST be a single word, which is one of the allowed categories. Do NOT include any other text, explanation, or punctuation.

    <transaction_data>
    {json.dumps(transaction_data, indent=2)}
    </transaction_data>

    Category:"""

    # Prepare the request body
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": [{ "type": "text", "text": prompt}]
            }
        ]
    })

    print("🤖 Sending data to Bedrock for classification...")

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

    # Extract the category (now expecting only the category name)
    category = completion

    return {"category": category}


if __name__ == "__main__":
    # Example usage with a sample receipt
    sample_receipt = [
        {
            "vendor": "THE CORNER STORE",
            "date": "2023-10-26",
            "total": "$12.34",
            "items": [
                {"description": "SANDWICH", "price": "$8.50"},
                {"description": "COFFEE", "price": "$3.84"},
            ],
        }
    ]

    classification = classify_transaction(sample_receipt)

    print(f"✅ Transaction classified as: {classification['category']}")
    print(json.dumps(classification, indent=2))
