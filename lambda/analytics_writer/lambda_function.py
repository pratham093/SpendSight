import json
import boto3
import os
from datetime import datetime

s3_client = boto3.client('s3')

ANALYTICS_BUCKET = os.environ['ANALYTICS_BUCKET']

def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] != 'INSERT':
            continue

        new_image = record['dynamodb']['NewImage']

        pk = new_image.get('PK', {}).get('S', '')
        vendor = new_image.get('vendor', {}).get('S', 'Unknown')
        amount = float(new_image.get('amount', {}).get('N', '0'))
        category = new_image.get('category', {}).get('S', 'Other')
        created_at = new_image.get('createdAt', {}).get('S', '')

        userid = pk.replace('USER#', '') if pk.startswith('USER#') else 'unknown'

        sk = new_image.get('SK', {}).get('S', '')
        expense_date = extract_date_from_sk(sk)

        if not expense_date:
            expense_date = datetime.utcnow().strftime('%Y-%m-%d')

        parts = expense_date.split('-')
        year = parts[0] if len(parts) >= 1 else '2026'
        month = parts[1] if len(parts) >= 2 else '01'
        day = parts[2] if len(parts) >= 3 else '01'

        analytics_record = {
            'userid': userid,
            'vendor': vendor,
            'amount': amount,
            'category': category,
            'date': expense_date,
            'created_at': created_at
        }

        timestamp = int(datetime.utcnow().timestamp() * 1000)
        s3_key = f"year={year}/month={month}/day={day}/{timestamp}.json"

        s3_client.put_object(
            Bucket=ANALYTICS_BUCKET,
            Key=s3_key,
            Body=json.dumps(analytics_record),
            ContentType='application/json'
        )

        print(f"Written analytics: {s3_key} -> {analytics_record}")

    return {'statusCode': 200, 'body': 'OK'}

def extract_date_from_sk(sk):
    if sk.startswith('DATE#'):
        parts = sk.split('#')
        if len(parts) >= 2:
            return parts[1]
    return None
