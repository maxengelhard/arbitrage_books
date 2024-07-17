import os
import json
import boto3
import requests
from lambda_decorators import load_json_body

def send_telegram_message(chat_id, text):
    try:
        token = os.getenv('telegram_token')
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

def delete_telegram_message(chat_id, message_id):
    try:
        token = os.getenv('telegram_token')
        url = f'https://api.telegram.org/bot{token}/deleteMessage'
        payload = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

def handle_delete_callback(callback_query):
    try:
        message = callback_query['message']
        chat_id = message['chat']['id']
        message_id = message['message_id']
        
        delete_response = delete_telegram_message(chat_id, message_id)
        return delete_response
    except Exception as e:
        print(f"Error handling delete callback: {e}")
        return None

def handle_keepa_message():
    try:
        print('handling keepa message')
    except Exception as e:
        print(f"Error handling keepa message: {e}")


@load_json_body
def lambda_handler(event, context):
    print(event)
    try:
        body = event['body']

        if 'message' in body:
            message = body['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')

            if text == '/ebay':
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

                except Exception as e:
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
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
