import boto3
import json
import os

# ---------- CONFIGURATION ----------
REGION = "us-east-1"        # Change if needed
IMAGE_FILE = "receipt3.jpg"  # Your receipt image filename
OUTPUT_FILE = "receipt_data.json"
# ----------------------------------

# Initialize the Textract client
textract = boto3.client("textract", region_name=REGION)

def extract_receipt_data(image_path):
    """Extract structured expense data from a receipt image using AWS Textract."""
    with open(image_path, "rb") as document:
        image_bytes = document.read()

    print("🧾 Sending image to Textract for analysis...")

    # Call Textract AnalyzeExpense API (best for receipts/invoices)
    response = textract.analyze_expense(Document={'Bytes': image_bytes})

    # Parse the response into a structured format
    extracted_data = []

    for doc in response.get("ExpenseDocuments", []):
        vendor = None
        total = None
        date = None
        items = []

        # --- Extract summary fields ---
        for field in doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            field_value = field.get("ValueDetection", {}).get("Text", "")
            if field_type == "VENDOR_NAME":
                vendor = field_value
            elif field_type == "TOTAL":
                total = field_value
            elif field_type == "INVOICE_RECEIPT_DATE":
                date = field_value

        # --- Extract line items ---
        for group in doc.get("LineItemGroups", []):
            for line_item in group.get("LineItems", []):
                item_name = None
                item_price = None
                for field in line_item.get("LineItemExpenseFields", []):
                    item_type = field.get("Type", {}).get("Text", "")
                    item_value = field.get("ValueDetection", {}).get("Text", "")
                    if item_type == "ITEM":
                        item_name = item_value
                    elif item_type in ["PRICE", "AMOUNT"]:
                        item_price = item_value
                if item_name:
                    items.append({
                        "description": item_name,
                        "price": item_price
                    })

        receipt = {
            "vendor": vendor,
            "date": date,
            "total": total,
            "items": items
        }
        extracted_data.append(receipt)

    return extracted_data


if __name__ == "__main__":
    if not os.path.exists(IMAGE_FILE):
        print(f"❌ File '{IMAGE_FILE}' not found! Please place your receipt image in this folder.")
        exit(1)

    data = extract_receipt_data(IMAGE_FILE)

    # Save results as JSON
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Extracted data saved to '{OUTPUT_FILE}'")
    print(json.dumps(data, indent=2))


