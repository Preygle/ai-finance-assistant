import os
import io
import boto3
from PIL import Image
from datetime import datetime
import logging
import re
from decimal import Decimal

from .extract_receipt import extract_receipt_data
from .classifier import classify_transaction

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# AWS Config - assuming these are set in the main app's .env file
REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")

# Initialize AWS clients
s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

def _upload_to_s3(file_stream, user_id):
    """Compresses and uploads a file-like object to S3, returning the key."""
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET environment variable is not set.")

    file_ext = file_stream.filename.rsplit('.', 1)[1].lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"receipt_{user_id}_{timestamp}.{file_ext}"
    s3_key = f"receipts/{filename}"

    logging.info(f"Uploading to S3 bucket '{S3_BUCKET}' with key '{s3_key}'")

    if file_ext != 'pdf':
        img = Image.open(file_stream)
        img.thumbnail((1024, 1024))
        buffer = io.BytesIO()
        img_format = img.format if img.format in ['JPEG', 'PNG'] else 'JPEG'
        img.save(buffer, format=img_format, quality=85, optimize=True)
        buffer.seek(0)
        s3.upload_fileobj(buffer, S3_BUCKET, s3_key)
    else:
        s3.upload_fileobj(file_stream, S3_BUCKET, s3_key)

    logging.info("S3 upload successful")
    return s3_key

def process_receipt(file_stream, user_id):
    """
    Orchestrates the receipt processing workflow.
    1. Uploads image to S3.
    2. Extracts data with Textract.
    3. Classifies with Bedrock.
    4. Saves to DynamoDB.
    5. Cleans and returns structured data for SQL DB.
    """
    try:
        s3_key = _upload_to_s3(file_stream, user_id)

        logging.info("Reading file back from S3 for Textract processing")
        s3_object = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        image_bytes = s3_object['Body'].read()

        logging.info("Starting receipt data extraction with Textract")
        extracted_data = extract_receipt_data(io.BytesIO(image_bytes))
        logging.info(f"Extracted data: {extracted_data}")

        if not extracted_data or not extracted_data[0]:
            logging.error("Could not extract any data from the receipt.")
            return None

        receipt_info = extracted_data[0]

        logging.info("Starting transaction classification with Bedrock")
        classification = classify_transaction(receipt_info)
        category = classification.get('category', 'Other')
        logging.info(f"Classification result: {category}")

        total_str = receipt_info.get('total', '0')
        total_cleaned = re.sub(r'[^\d,.]', '', total_str).replace(',', '.') if total_str else '0'
        total = float(Decimal(total_cleaned) if total_cleaned else Decimal('0'))

        date_str = receipt_info.get('date')
        try:
            transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            try:
                transaction_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            except (ValueError, TypeError):
                transaction_date = datetime.now().date()

        # --- Return data for SQL database ---
        final_transaction = {
            'merchant': receipt_info.get('vendor', 'Unknown Merchant'),
            'amount': total,
            'date': transaction_date,
            'category': category,
            'description': f"Receipt from {receipt_info.get('vendor', 'N/A')}",
            'source': 'receipt'
        }

        logging.info(f"Processed transaction data: {final_transaction}")
        return final_transaction

    except Exception as e:
        logging.error(f"An error occurred during receipt processing: {e}", exc_info=True)
        return None
