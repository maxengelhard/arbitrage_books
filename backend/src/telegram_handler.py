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

def format_keepa_message(data):
    try:
        asin = data.get('asin')
        tracking_list_name = data.get('trackingListName', 'N/A')
        meta_data = data.get('metaData', 'N/A')
        is_active = data.get('isActive', False)
        is_active_str = 'Active' if is_active else 'Inactive'
        threshold_values = data.get('thresholdValues', [])
        notify_if = data.get('notifyIf', [])

        message = f"<b>Keepa Tracking Notification</b>\n"
        message += f"<b>ASIN:</b> {asin}\n"
        message += f"<b>Tracking List:</b> {tracking_list_name}\n"
        message += f"<b>Metadata:</b> {meta_data}\n"
        message += f"<b>Status:</b> {is_active_str}\n"

        if threshold_values:
            message += f"\n<b>Threshold Values:</b>\n"
            for value in threshold_values:
                domain = value.get('domain', 'N/A')
                csv_type = value.get('csvType', 'N/A')
                is_drop = value.get('isDrop', False)
                direction = 'Drop' if is_drop else 'Increase'
                message += f" - Domain: {domain}, Type: {csv_type}, Direction: {direction}\n"

        if notify_if:
            message += f"\n<b>Notification If:</b>\n"
            for notify in notify_if:
                domain = notify.get('domain', 'N/A')
                csv_type = notify.get('csvType', 'N/A')
                notify_if_type = notify.get('notifyIfType', 'N/A')
                notify_type_str = 'Out of Stock' if notify_if_type == 0 else 'Back in Stock'
                message += f" - Domain: {domain}, Type: {csv_type}, Notify If: {notify_type_str}\n"

        return message
    except Exception as e:
        print(f"Error formatting Keepa message: {e}")
        return "Error formatting Keepa notification."

def handle_keepa_message(data, chat_id):
    try:
        message = format_keepa_message(data)
        send_telegram_message(chat_id, message)
    except Exception as e:
        print(f"Error handling Keepa message: {e}")


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

        elif 'asin' in body: # keepa notification
            chat_id = os.getenv('chat_id')  # Ensure you have this environment variable set
            handle_keepa_message(body, chat_id)

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
