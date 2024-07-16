import os
import json
import requests
from lambda_decorators import load_json_body

def delete_telegram_message(chat_id, message_id):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/deleteMessage'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    response = requests.post(url, data=payload)
    return response.json()

@load_json_body
def lambda_handler(event, context):
    body = event['body']
    
    if 'callback_query' in body:
        callback_query = body['callback_query']
        message = callback_query['message']
        chat_id = message['chat']['id']
        message_id = message['message_id']
        
        if 'data' in callback_query and callback_query['data'].startswith('delete_'):
            delete_response = delete_telegram_message(chat_id, message_id)
            return {
                'statusCode': 200,
                'body': json.dumps(delete_response)
            }

    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Invalid request'})
    }
