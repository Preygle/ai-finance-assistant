"""AWS Bedrock integration helper (non-blocking / optional).

This module provides a small helper to call AWS Bedrock's runtime API using boto3.

Usage notes:
- Install dependencies: `pip install -r requirements.txt` (we added `boto3`).
- Configure AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) and AWS_REGION in your environment, or use an IAM role if running on an AWS host.
- The helper calls the model ID: 'anthropic.claude-3-sonnet-20240229-v1:0' by default. Change `model_id` if you want a different model.
- This function performs a single `invoke_model` call and returns the model's text output.

Security: Do not commit credentials. Keep them in environment or use an IAM role.

Note: This code only prepares and performs the SDK call locally. It won't execute unless you run it in an environment with valid AWS credentials and network access to Bedrock.
"""
from typing import Optional
import os
import json
import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"


def generate_insights_bedrock(prompt: str, model_id: str = DEFAULT_MODEL_ID, max_tokens: int = 1024) -> str:
    """Invoke AWS Bedrock model and return generated text.

    Args:
        prompt: The input prompt to send to the model (string).
        model_id: Bedrock model identifier. Default uses the Claude model requested.
        max_tokens: Soft limit for the response size.

    Returns:
        The text output from the model.

    Raises:
        RuntimeError on failures with diagnostic information.
    """
    # DRY-RUN mode for local testing without AWS credentials
    if os.environ.get('BEDROCK_DRY_RUN', '').lower() in ('1', 'true', 'yes'):
        # Return a canned JSON-like text that the caller can parse
        canned = {
            "patterns": [
                "Top spending category: Dining (₹12,345)",
                "Average transaction size: ₹2,345",
                "Most transactions occur on weekends",
                "Recurring subscription detected: Streaming service (₹499/month)",
                "One-off large purchase in Electronics category"
            ],
            "recommendations": [
                "Reduce dining out by 20% to save ~₹2,400/month",
                "Re-evaluate streaming subscriptions and consolidate plans",
                "Set up a weekly grocery budget to reduce impulse buys",
                "Automate savings: transfer 10% of income into savings account",
                "Negotiate or switch utility providers for lower rates"
            ],
            "opportunities": [
                "Potential savings in dining category - Consider meal planning",
                "Recurring subscriptions optimization opportunity",
                "Energy bill savings through smart home devices",
                "Cashback opportunities on current spending patterns",
                "Bulk purchase opportunities for frequent items"
            ]
        }
        return json.dumps(canned)

    # Validate environment for real Bedrock call
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("AWS region not found in environment. Set AWS_REGION or AWS_DEFAULT_REGION.")

    try:
        client = boto3.client("bedrock-runtime", region_name=region)

        # Build the payload for Claude 3 using the anthropic format
        input_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        body = json.dumps(input_payload).encode("utf-8")

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json"
        )

        # The response body can be bytes; decode and parse if JSON
        raw_body = response.get("body")
        if isinstance(raw_body, (bytes, bytearray)):
            decoded = raw_body.decode("utf-8")
        else:
            decoded = str(raw_body)

        # Parse Claude 3's response format
        try:
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                # Claude 3 response format
                if 'content' in parsed and isinstance(parsed['content'], list):
                    for content_item in parsed['content']:
                        if isinstance(content_item, dict) and content_item.get('type') == 'text':
                            return content_item.get('text', '')
                # Fallback: return the whole response as string
                return json.dumps(parsed)
        except (ValueError, TypeError):
            # Not JSON; return decoded text
            return decoded

    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Bedrock invocation failed: {e}")


if __name__ == "__main__":
    # Simple interactive test runner (for local manual testing only).
    prompt = input("Enter a short prompt for the Bedrock model: ")
    try:
        print("Invoking Bedrock model... (ensure AWS credentials & region are configured)")
        out = generate_insights_bedrock(prompt)
        print("--- Model output ---")
        print(out)
    except Exception as exc:
        print("Error:", exc)
