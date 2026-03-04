import json
import boto3
import os
import time

athena_client = boto3.client('athena')

ATHENA_DATABASE = os.environ['ATHENA_DATABASE']
ATHENA_OUTPUT_LOCATION = os.environ['ATHENA_OUTPUT_LOCATION']

def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return response(200, {})

    query_params = event.get('queryStringParameters') or {}
    user_id = query_params.get('userId', '').strip().lower()

    if not user_id:
        return response(401, {'error': 'Missing userId parameter'})

    query_type = query_params.get('type', 'summary')
    year = query_params.get('year', '2026')
    month = query_params.get('month', '')

    try:
        if query_type == 'summary':
            result = get_summary(year, month, user_id)
        elif query_type == 'monthly_trend':
            result = get_monthly_trend(year, user_id)
        elif query_type == 'category_breakdown':
            result = get_category_breakdown(year, month, user_id)
        elif query_type == 'top_vendors':
            result = get_top_vendors(year, month, user_id)
        elif query_type == 'daily_spending':
            result = get_daily_spending(year, month, user_id)
        else:
            result = {'error': 'Unknown query type'}

        return response(200, result)
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {'error': str(e)})

def execute_query(query):
    resp = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': ATHENA_DATABASE},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
    )

    query_execution_id = resp['QueryExecutionId']

    max_attempts = 30
    for attempt in range(max_attempts):
        status_response = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status = status_response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            error = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            raise Exception(f"Query {status}: {error}")

        time.sleep(0.5)
    else:
        raise Exception("Query timeout")

    results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
    return parse_results(results)

def parse_results(results):
    rows = results['ResultSet']['Rows']
    if len(rows) <= 1:
        return []

    headers = [col['VarCharValue'] for col in rows[0]['Data']]

    data = []
    for row in rows[1:]:
        values = [col.get('VarCharValue', '') for col in row['Data']]
        data.append(dict(zip(headers, values)))

    return data

def build_where(year, month, user_id):
    clauses = [f"year = '{year}'", f"userid = '{user_id}'"]
    if month:
        clauses.append(f"month = '{month}'")
    return "WHERE " + " AND ".join(clauses)

def get_summary(year, month, user_id):
    where = build_where(year, month, user_id)

    query = f"""
        SELECT
            COUNT(*) as total_transactions,
            COALESCE(SUM(amount), 0) as total_spending,
            COALESCE(AVG(amount), 0) as avg_transaction,
            COUNT(DISTINCT vendor) as unique_vendors
        FROM expenses
        {where}
    """

    results = execute_query(query)
    if results:
        row = results[0]
        return {
            'summary': {
                'total_transactions': int(row.get('total_transactions', 0)),
                'total_spending': float(row.get('total_spending', 0)),
                'avg_transaction': float(row.get('avg_transaction', 0)),
                'unique_vendors': int(row.get('unique_vendors', 0))
            }
        }
    return {'summary': {}}

def get_monthly_trend(year, user_id):
    query = f"""
        SELECT
            month,
            SUM(amount) as monthly_total,
            COUNT(*) as transaction_count
        FROM expenses
        WHERE year = '{year}' AND userid = '{user_id}'
        GROUP BY month
        ORDER BY month
    """

    results = execute_query(query)
    formatted = []
    for row in results:
        formatted.append({
            'month': row.get('month', ''),
            'monthly_total': float(row.get('monthly_total', 0)),
            'transaction_count': int(row.get('transaction_count', 0))
        })

    return {'monthly_trend': formatted}

def get_category_breakdown(year, month, user_id):
    where = build_where(year, month, user_id)

    query = f"""
        SELECT
            category,
            SUM(amount) as total_amount,
            COUNT(*) as count
        FROM expenses
        {where}
        GROUP BY category
        ORDER BY total_amount DESC
    """

    results = execute_query(query)
    formatted = []
    for row in results:
        formatted.append({
            'category': row.get('category', 'Other'),
            'total_amount': float(row.get('total_amount', 0)),
            'count': int(row.get('count', 0))
        })

    return {'category_breakdown': formatted}

def get_top_vendors(year, month, user_id, limit=10):
    where = build_where(year, month, user_id)

    query = f"""
        SELECT
            vendor,
            SUM(amount) as total_spent,
            COUNT(*) as visit_count
        FROM expenses
        {where}
        GROUP BY vendor
        ORDER BY total_spent DESC
        LIMIT {limit}
    """

    results = execute_query(query)
    formatted = []
    for row in results:
        formatted.append({
            'vendor': row.get('vendor', 'Unknown'),
            'total_spent': float(row.get('total_spent', 0)),
            'visit_count': int(row.get('visit_count', 0))
        })

    return {'top_vendors': formatted}

def get_daily_spending(year, month, user_id):
    if not month:
        month = '01'

    query = f"""
        SELECT
            day,
            SUM(amount) as daily_total,
            COUNT(*) as transaction_count
        FROM expenses
        WHERE year = '{year}' AND month = '{month}' AND userid = '{user_id}'
        GROUP BY day
        ORDER BY day
    """

    results = execute_query(query)
    formatted = []
    for row in results:
        formatted.append({
            'day': row.get('day', ''),
            'daily_total': float(row.get('daily_total', 0)),
            'transaction_count': int(row.get('transaction_count', 0))
        })

    return {'daily_spending': formatted}

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body)
    }
