import os
import tempfile
import re
import logging
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
import boto3
from datetime import datetime, timedelta
import json
from decimal import Decimal
from PIL import Image
from extract_receipt import extract_receipt_data
from classifier import classify_transaction
from dotenv import load_dotenv

load_dotenv()

"""
Configuration is centralized via environment variables. Create a .env file locally
and export these values in production.

Required env vars (examples):
  AWS_REGION=us-east-1
  S3_BUCKET=your-receipts-bucket-name  # TODO: replace with your S3 bucket name
  DYNAMODB_TABLE=your-dynamodb-table-name  # TODO: replace with your DynamoDB table
  FLASK_SECRET_KEY=dev-secret
"""

# ------------------- CONFIG -------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# Hardcoded user credentials
USERS = {
    "owais": "Owais@1234",
    "achal": "Achal@1234",
    "abhay": "Abhay@1234"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# AWS Config
REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "your-receipts-bucket-name")  # TODO: set your bucket
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "your-dynamodb-table-name")  # TODO: set your table

# Initialize AWS clients
s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

# ------------------------------------------------


@app.route('/test_dynamo')
def test_dynamo():
    try:
        response = table.scan(Limit=1)
        return jsonify({"status": "success", "count": len(response.get('Items', []))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        logging.info("--- Upload request received ---")
        if 'receipt' not in request.files:
            logging.warning("No file part in request")
            return redirect(request.url)
        file = request.files['receipt']
        if file.filename == '':
            logging.warning("No selected file")
            return redirect(request.url)
        if file:
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            logging.info(f"File received: {file.filename}")
            if file_ext not in ['jpg', 'jpeg', 'png', 'pdf']:
                logging.warning(f"Unsupported file format: {file_ext}")
                return "❌ Unsupported file format. Please upload a JPG, PNG, or PDF.", 400

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"receipt_{timestamp}.{file_ext}"

            try:
                # ✅ Compress and Upload to S3
                s3_key = f"receipts/{filename}"
                logging.info(f"Uploading to S3 bucket '{S3_BUCKET}' with key '{s3_key}'")

                if file_ext != 'pdf':
                    # Compress image
                    img = Image.open(file)
                    img.thumbnail((1024, 1024))
                    buffer = io.BytesIO()
                    img.save(buffer, format=img.format, quality=85)
                    buffer.seek(0)
                    s3.upload_fileobj(buffer, S3_BUCKET, s3_key)
                else:
                    # For PDFs, upload directly
                    s3.upload_fileobj(file, S3_BUCKET, s3_key)

                logging.info("S3 upload successful")

                # ✅ Read back from S3 for Textract
                logging.info("Reading file back from S3 for processing")
                s3_object = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
                image_bytes = s3_object['Body'].read()

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_image_path = os.path.join(tmpdir, filename)
                    with open(tmp_image_path, "wb") as f:
                        f.write(image_bytes)

                    logging.info("Starting receipt data extraction with Textract")
                    extracted_data = extract_receipt_data(tmp_image_path)
                    logging.info(f"Extracted data: {json.dumps(extracted_data, indent=2)}")

                if not extracted_data:
                    logging.error("Could not extract data from receipt")
                    return "❌ Could not extract data from receipt", 400

                logging.info("Starting transaction classification with Bedrock")
                classification = classify_transaction(extracted_data[0])
                logging.info(f"Classification result: {json.dumps(classification, indent=2)}")

                receipt_id = filename.split('.')[0]
                user = "local_user" # Hardcoded user for local use
                now = datetime.now()
                date_str = extracted_data[0].get('date')
                try:
                    date = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d') # Storing in YYYY-MM-DD
                except (ValueError, TypeError):
                    date = now.strftime('%Y-%m-%d')

                time = now.strftime('%H:%M:%S')
                category = classification.get('category')

                total_str = extracted_data[0].get('total', '0')
                total_cleaned = re.sub(r'[^\d,.]', '', total_str).replace(',', '.')
                total = Decimal(total_cleaned) if total_cleaned else Decimal('0')

                items = extracted_data[0].get('items', [])
                for item in items:
                    price_str = item.get('price', '0')
                    price_cleaned = re.sub(r'[^\d,.]', '', price_str).replace(',', '.')
                    item['price'] = Decimal(price_cleaned) if price_cleaned else Decimal('0')

                item_to_save = {
                    'receipt': receipt_id,
                    'user': user,
                    'date': date,
                    'time': time,
                    'category': category,
                    'total': total,
                    'items': items,
                    's3_key': s3_key
                }
                logging.info(f"Saving item to DynamoDB: {json.dumps(item_to_save, default=str, indent=2)}")

                table.put_item(Item=item_to_save)
                logging.info("Successfully saved item to DynamoDB")
                session['new_receipt_uploaded'] = True

            except Exception as e:
                logging.error(f"An error occurred: {e}", exc_info=True)
                return f"Error uploading or processing receipt: {e}", 500

            logging.info("--- Upload request finished ---Redirecting to dashboard.")
            return redirect(url_for('dashboard'))

    return render_template('upload.html')

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and USERS[username] == password:
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    user = "local_user"  # Hardcoded user for local use

    try:
        response = table.query(
            IndexName='user-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user').eq(user)
        )
        all_receipts = response.get('Items', [])
    except Exception as e:
        print(f"Error fetching from DynamoDB: {e}")
        all_receipts = []

    # Get filter values from request
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    category = request.args.get('category')
    period = request.args.get('period')

    # Filter receipts
    filtered_receipts = all_receipts

    if category:
        filtered_receipts = [r for r in filtered_receipts if r.get('category') == category]

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        filtered_receipts = [r for r in filtered_receipts if start_date <= datetime.strptime(r['date'], '%Y-%m-%d') <= end_date]
    elif period:
        end_date = datetime.now()
        if period == 'week':
            start_date = end_date - timedelta(days=end_date.weekday())
        elif period == 'month':
            start_date = end_date.replace(day=1)
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1)
        else:
            start_date = end_date - timedelta(days=7)
        
        filtered_receipts = [r for r in filtered_receipts if start_date <= datetime.strptime(r['date'], '%Y-%m-%d') <= end_date]

    # Get unique categories for dropdown
    categories = sorted(list(set(r.get('category') for r in all_receipts if r.get('category'))))

    # Prepare receipts for rendering
    for receipt in filtered_receipts:
        if 'total' in receipt:
            receipt['total'] = str(receipt['total'])
        if 'items' in receipt:
            for item in receipt['items']:
                if 'price' in item:
                    item['price'] = str(item['price'])
        if 's3_key' in receipt:
            receipt['s3_url'] = s3.generate_presigned_url('get_object',
                                                                  Params={'Bucket': S3_BUCKET,
                                                                          'Key': receipt['s3_key']},
                                                                  ExpiresIn=3600)
        if 'date' in receipt and receipt['date']:
            try:
                dt_object = datetime.strptime(receipt['date'], '%Y-%m-%d')
                receipt['date'] = dt_object.strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                logging.warning(f"Could not format date for receipt {receipt.get('receipt_id')}: {receipt['date']}")
        if 'time' in receipt and receipt['time']:
            try:
                dt_object = datetime.strptime(receipt['time'], '%H:%M:%S')
                receipt['time'] = dt_object.strftime('%I:%M %p')
            except (ValueError, TypeError):
                logging.warning(f"Could not format time for receipt {receipt.get('receipt_id')}: {receipt['time']}")

    return render_template('dashboard.html', 
                           receipts=filtered_receipts, 
                           categories=categories,
                           selected_category=category,
                           start_date=start_date_str,
                           end_date=end_date_str)

@app.route('/delete_receipt/<receipt_id>', methods=['POST'])
def delete_receipt(receipt_id):

    try:

        # Get the receipt from DynamoDB to get the s3_key

        response = table.get_item(Key={'receipt': receipt_id})

        receipt = response.get('Item')

        if receipt and 's3_key' in receipt:

            # Delete from S3

            s3.delete_object(Bucket=S3_BUCKET, Key=receipt['s3_key'])

            logging.info(f"Deleted {receipt['s3_key']} from S3.")

        # Delete from DynamoDB

        table.delete_item(Key={'receipt': receipt_id})

        logging.info(f"Deleted {receipt_id} from DynamoDB.")

        flash('Receipt deleted successfully.', 'success')

    except Exception as e:

        logging.error(f"Error deleting receipt {receipt_id}: {e}")

        flash('Error deleting receipt.', 'danger')

    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
