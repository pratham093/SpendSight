import json
import boto3
import os
import uuid
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

RECEIPT_BUCKET = os.environ['RECEIPT_BUCKET']
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    http_method = event['httpMethod']
    path = event['path']

    if http_method == 'OPTIONS':
        return response(200, {})

    query_params = event.get('queryStringParameters') or {}
    user_email = query_params.get('userId', '').strip().lower()

    if not user_email:
        return response(401, {'error': 'Missing userId parameter'})

    user_key = f"USER#{user_email}"
    safe_email = user_email.replace('@', '_at_').replace('.', '_')

    if path == '/upload-url' and http_method == 'POST':
        return generate_presigned_url(event, safe_email)
    elif path == '/expenses' and http_method == 'GET':
        return get_expenses(event, user_key)
    elif path == '/expenses' and http_method == 'POST':
        return add_expense_manual(event, user_key)
    else:
        return response(404, {'error': 'Not found'})

def generate_presigned_url(event, safe_email):
    body = json.loads(event.get('body', '{}'))
    filename = body.get('filename', 'receipt.jpg')
    content_type = body.get('contentType', 'image/jpeg')

    timestamp = datetime.utcnow()
    year = timestamp.strftime('%Y')
    month = timestamp.strftime('%m')
    unique_id = str(uuid.uuid4())[:8]

    safe_filename = ''.join(c for c in filename if c.isalnum() or c in '.-_')
    s3_key = f"receipts/{safe_email}/{year}/{month}/{unique_id}_{safe_filename}"

    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': RECEIPT_BUCKET,
            'Key': s3_key,
            'ContentType': content_type
        },
        ExpiresIn=300
    )

    return response(200, {
        'uploadUrl': presigned_url,
        's3Key': s3_key,
        'expiresIn': 300
    })

def get_expenses(event, user_key):
    table = dynamodb.Table(TABLE_NAME)

    query_params = event.get('queryStringParameters') or {}

    end_date = query_params.get('endDate', datetime.utcnow().strftime('%Y-%m-%d'))
    start_date = query_params.get('startDate',
        (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'))

    result = table.query(
        KeyConditionExpression=Key('PK').eq(user_key) &
            Key('SK').between(f"DATE#{start_date}", f"DATE#{end_date}~"),
        ScanIndexForward=False,
        Limit=100
    )

    expenses = []
    for item in result.get('Items', []):
        expenses.append({
            'id': item['SK'],
            'vendor': item.get('vendor', 'Unknown'),
            'amount': float(item.get('amount', 0)),
            'currency': item.get('currency', 'USD'),
            'category': item.get('category', 'Other'),
            'date': item.get('createdAt', ''),
            's3Key': item.get('s3Key', '')
        })

    return response(200, {'expenses': expenses})

def add_expense_manual(event, user_key):
    from decimal import Decimal

    table = dynamodb.Table(TABLE_NAME)
    body = json.loads(event.get('body', '{}'))

    vendor = body.get('vendor', 'Unknown')
    amount = float(body.get('amount', 0))
    category = body.get('category', 'Other')
    expense_date = body.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    s3_key = body.get('s3Key', '')

    timestamp = int(datetime.utcnow().timestamp())
    sort_key = f"DATE#{expense_date}#TS#{timestamp}"

    item = {
        'PK': user_key,
        'SK': sort_key,
        'vendor': vendor,
        'amount': Decimal(str(round(amount, 2))),
        'currency': 'USD',
        'category': category,
        'createdAt': datetime.utcnow().isoformat() + 'Z',
        's3Key': s3_key
    }

    table.put_item(Item=item)

    return response(201, {
        'message': 'Expense added successfully',
        'expense': {
            'id': sort_key,
            'vendor': vendor,
            'amount': amount,
            'category': category,
            'date': expense_date
        }
    })

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body)
    }
