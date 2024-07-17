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

    # Ensure body is not None
    if body is None:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Empty body received'})
        }
    
    if 'message' in body:
        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        if text == '/ebay':
            start_response = send_telegram_message(chat_id, "The eBay data gathering process has started.")
            start_message_id = start_response['result']['message_id']

            return {
               'stopping' 
            }

            try:
                client = boto3.client('lambda')
                function_name = os.getenv('gather_data_function')

                # Create the payload to send to the gather_data_function
                payload = {
                    'chat_id': chat_id,
                }
                
                response = client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',  # Asynchronous invocation
                    Payload=json.dumps(payload)  # Sending event data
                )

                # Check if invocation was successful
                if response['StatusCode'] != 202:
                    raise Exception(f"Failed to invoke gather_data_function: {response}")

                # The completion message will be handled in the gather_data_function
            except Exception as e:
                # Log the exception and notify via Telegram
                print(f"Error invoking gather_data_function: {e}")
                send_telegram_message(chat_id, "An error occurred while starting the eBay data gathering process.")
    
    elif 'callback_query' in body:
        callback_query = body['callback_query']
        if 'data' in callback_query and callback_query['data'].startswith('delete_'):
            delete_response = handle_delete_callback(callback_query)
            return {
                'statusCode': 200,
                'body': json.dumps(delete_response)
            }

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'No action taken'})
    }
