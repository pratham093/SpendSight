import json
import boto3
import os
import re
import base64
import urllib.request
import urllib.error
import time
from datetime import datetime
from decimal import Decimal

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

TABLE_NAME = os.environ['TABLE_NAME']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

MAX_RETRIES = 3
RETRY_STATUS_CODES = [429, 503]

def lambda_handler(event, context):

    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        if key.endswith('/'):
            continue

        print(f"Processing receipt: s3://{bucket}/{key}")

        user_key = extract_user_key(key)
        print(f"User key: {user_key}")

        try:
            expense_data = process_receipt_with_gemini(bucket, key)

            if expense_data:
                saved_item = save_to_dynamodb(expense_data, key, user_key)
                print(f"Successfully saved expense: {saved_item}")
            else:
                print(f"Could not extract data, saving with defaults")
                save_fallback_expense(key, user_key)

        except Exception as e:
            print(f"Error processing receipt: {str(e)}")
            save_fallback_expense(key, user_key)

    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }

def extract_user_key(s3_key):
    parts = s3_key.split('/')
    if len(parts) >= 2:
        safe_email = parts[1]
        email = safe_email.replace('_at_', '@').replace('_', '.', safe_email.count('_') - safe_email.count('_at_'))
        if '_at_' in safe_email:
            at_pos = safe_email.index('_at_')
            local = safe_email[:at_pos]
            domain = safe_email[at_pos + 4:]
            email = f"{local}@{domain}".replace('_', '.')
            return f"USER#{email}"
        if safe_email == 'demo':
            return 'USER#DEMO'
    return 'USER#DEMO'

def call_gemini_with_retry(req_url, req_body):

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            req_url,
            data=json.dumps(req_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            status_code = e.code

            if status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES - 1:
                retry_after = e.headers.get('Retry-After')
                if retry_after:
                    wait_time = min(int(retry_after), 45)
                else:
                    wait_time = (2 ** attempt) * 5

                print(f"Attempt {attempt + 1}/{MAX_RETRIES}: Got {status_code}, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue

            print(f"Gemini API error: {status_code} - {error_body}")
            raise Exception(f"Gemini API failed: {status_code}")

        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = (2 ** attempt) * 5
                print(f"Attempt {attempt + 1}/{MAX_RETRIES}: Network error, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"Network error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")

    raise Exception("All retry attempts exhausted")

def process_receipt_with_gemini(bucket, key):

    print("Step 1: Downloading image from S3...")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    image_bytes = response['Body'].read()

    print("Step 2: Converting image to base64...")
    base64_image = base64.standard_b64encode(image_bytes).decode('utf-8')

    file_extension = key.split('.')[-1].lower()
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    mime_type = mime_types.get(file_extension, 'image/jpeg')

    print("Step 3: Sending to Gemini Vision API...")

    prompt = """You are a receipt parser. Look at this receipt image and extract the following information.

Return ONLY a valid JSON object with exactly these fields:
{
    "vendor": "Store or restaurant name (clean and capitalize properly)",
    "amount": 0.00,
    "date": "YYYY-MM-DD",
    "category": "Category name"
}

Rules:
1. vendor: Extract the store/restaurant name. Clean it up (e.g., "STARBUCKS #1234" becomes "Starbucks")
2. amount: Extract the TOTAL amount (the final amount paid). Numbers only, no currency symbols.
3. date: Convert to YYYY-MM-DD format. If you can't find a date, use today's date.
4. category: Choose ONE from: Food, Groceries, Transportation, Shopping, Entertainment, Utilities, Healthcare, Other

Examples of category:
- Starbucks, McDonald's, restaurants → Food
- Walmart grocery, Kroger, supermarkets → Groceries
- Gas stations, Uber, parking → Transportation
- Amazon, clothing stores, electronics → Shopping
- Netflix, movie theaters, games → Entertainment
- Electric bill, phone bill, internet → Utilities
- Pharmacy, doctor, hospital → Healthcare
- Anything else → Other

IMPORTANT: Return ONLY the JSON object. No explanation, no markdown, no code blocks. Just the raw JSON."""

    request_body = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64_image
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 500,
            "responseMimeType": "application/json"
        }
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    response_data = call_gemini_with_retry(url, request_body)

    print(f"Step 4: Parsing Gemini response...")

    try:
        gemini_text = response_data['candidates'][0]['content']['parts'][0]['text']
        print(f"Gemini raw response: {gemini_text}")

        clean_text = gemini_text.strip()

        if clean_text.startswith('```'):
            clean_text = clean_text.replace('```json', '').replace('```', '').strip()

        expense_data = json.loads(clean_text)

        expense_data['vendor'] = str(expense_data.get('vendor', 'Unknown Vendor')).strip()
        expense_data['amount'] = float(expense_data.get('amount', 0))
        expense_data['category'] = str(expense_data.get('category', 'Other')).strip()

        if not expense_data.get('date'):
            expense_data['date'] = datetime.utcnow().strftime('%Y-%m-%d')

        valid_categories = ['Food', 'Groceries', 'Transportation', 'Shopping',
                          'Entertainment', 'Utilities', 'Healthcare', 'Other']
        if expense_data['category'] not in valid_categories:
            expense_data['category'] = 'Other'

        print(f"Extracted data: {expense_data}")
        return expense_data

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Failed to parse Gemini response: {str(e)}")
        print(f"Response data: {response_data}")
        return None

def save_to_dynamodb(expense_data, s3_key, user_key):

    table = dynamodb.Table(TABLE_NAME)

    timestamp = int(datetime.utcnow().timestamp() * 1000)
    expense_date = expense_data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))

    sort_key = f"DATE#{expense_date}#TS#{timestamp}"

    item = {
        'PK': user_key,
        'SK': sort_key,
        'vendor': expense_data['vendor'],
        'amount': Decimal(str(round(expense_data['amount'], 2))),
        'currency': 'USD',
        'category': expense_data['category'],
        'createdAt': datetime.utcnow().isoformat() + 'Z',
        's3Key': s3_key
    }

    table.put_item(Item=item)
    print(f"Saved to DynamoDB: {item}")

    return item

def save_fallback_expense(s3_key, user_key):

    fallback_data = {
        'vendor': 'Unknown Vendor',
        'amount': 0.0,
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'category': 'Other'
    }

    return save_to_dynamodb(fallback_data, s3_key, user_key)
