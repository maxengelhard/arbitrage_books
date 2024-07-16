import os
import json
import boto3
import requests
from lambda_decorators import load_json_body

def send_telegram_message(chat_id, text):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    response = requests.post(url, data=payload)
    return response.json()

def delete_telegram_message(chat_id, message_id):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/deleteMessage'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    response = requests.post(url, data=payload)
    return response.json()

def handle_delete_callback(callback_query):
    message = callback_query['message']
    chat_id = message['chat']['id']
    message_id = message['message_id']
    
    delete_response = delete_telegram_message(chat_id, message_id)
    return delete_response

@load_json_body
def lambda_handler(event, context):
    print(event)
    body = event['body']
    
    if 'message' in body:
        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        if text == '/ebay':
            start_response = send_telegram_message(chat_id, "The eBay data gathering process has started.")
            start_message_id = start_response['result']['message_id']

            client = boto3.client('lambda')
            function_name = os.getenv('gather_data_function')
            
            response = client.invoke(
                FunctionName=function_name,
                InvocationType='Event'  # Asynchronous invocation
            )

            delete_telegram_message(chat_id, start_message_id)
            send_telegram_message(chat_id, "The eBay data gathering process is complete.")
    
    elif 'callback_query' in body:
        callback_query = body['callback_query']
        if 'data' in callback_query and callback_query['data'].startswith('delete_'):
            delete_response = handle_delete_callback(callback_query)
            return {
                'statusCode': 200,
                'body': json.dumps(delete_response)
            }

    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Invalid request'})
    }
