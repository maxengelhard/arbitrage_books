import os.path
import boto3
import re
import datetime
import json
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import requests
import keepa
from lambda_decorators import load_json_body
from amazon_seller_check import SellerClient
# from telegram import ParseMode
from dotenv import load_dotenv
load_dotenv()

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_secret_from_s3(bucket_name, key):
    try:
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=bucket_name, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching secret from S3: {e}")
        return None

def upload_secret_to_s3(bucket_name, key, data):
    try:
        s3 = boto3.client('s3')
        s3.put_object(Bucket=bucket_name, Key=key, Body=data)
    except Exception as e:
        print(f"Error uploading secret to S3: {e}")

def authenticate_gmail():
    try: 
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            elif os.path.exists('client_secret.json'):
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            else: # coming from lambda
                bucket_name = os.getenv('secrets_bucket')
                key = 'token.json'
                credentials_json = get_secret_from_s3(bucket_name, key)
                with open('/tmp/token.json', 'w') as creds_file:
                    creds_file.write(credentials_json)
                creds = Credentials.from_authorized_user_file('/tmp/token.json', SCOPES)
                if not creds.valid:
                    creds.refresh(Request())
                    upload_secret_to_s3(bucket_name, key, creds.to_json())
        return creds
    except Exception as e:
        print(f"Error authenticating Gmail: {e}")
        return None

def extract_asin(subject_line):
    try:
        parts = re.split('[:,]', subject_line)
        asin = parts[0].strip()
        if asin.isdigit():
            return asin[-10:]
        else:
            return None
    except Exception as e:
        print(f"Error extracting ASIN: {e}")
        return None

def get_emails_with_subject(service, subject, days):
    try:
        query = f'newer_than:{days}d'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        emails = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject_line = next(header['value'] for header in headers if header['name'] == 'Subject')
            
            if subject in subject_line:
                sender = next(header['value'] for header in headers if header['name'] == 'From')
                date = next(header['value'] for header in headers if header['name'] == 'Date')
                snippet = msg['snippet']
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/html':
                        data = part['body']['data']
                        html = base64.urlsafe_b64decode(data.encode('UTF-8')).decode('utf-8')
                        asin = extract_asin(subject_line)
                        if asin:
                            emails.append({
                                'ASIN': asin,
                                'amz_link': f'https://www.amazon.com/dp/{asin}',
                                'Subject': subject_line,
                                'From': sender,
                                'Date': date,
                                'Snippet': snippet,
                                'Html': html,
                            })
        return emails
    except Exception as e:
        print(f"Error getting emails with subject: {e}")
        return []

def parse_html(html):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        h1_tag = soup.find('h1')
        if h1_tag:
            a_tag = h1_tag.find('a')
            if a_tag and 'href' in a_tag.attrs:
                return a_tag['href']
        return None
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None


def get_keepa_prices(asins):
    try:
        api = keepa.Keepa(accesskey=os.getenv('keepa_api'),timeout=300)
        products = api.query(asins, only_live_offers=1, days=1,stats=180,buybox=1) # offers=20
        prices = {}

        for product in products:
            asin = product['asin']
            title = product['title']

            stats = product.get('stats',{})
            buybox_new_price = stats.get('buyBoxPrice', None)
            buybox_new_shipping = stats.get('buyBoxShipping', None)
            buybox_new_is_fba = stats.get('buyBoxIsFBA', None)
            
            buybox_used_price = stats.get('buyBoxUsedPrice', None)
            buybox_used_shipping = stats.get('buyBoxUsedShipping', None)
            buybox_used_is_fba = stats.get('buyBoxUsedIsFBA', None)
            
            
            new_price = float(buybox_new_price + buybox_new_shipping)/100 if buybox_new_price else None
            used_price = float(buybox_used_price + buybox_used_shipping)/100 if buybox_used_price else None

            max_new_price = round(new_price * .5,2) if new_price else None
            max_used_price = round(used_price * .5,2) if used_price else None
            
            prices[asin] = {
                'Title': title,
                'Keepa New Price': new_price,
                'Max New Price': max_new_price,
                'Keepa New Is FBA': buybox_new_is_fba,
                'Keepa Used Price': used_price,
                'Max Used Price': max_used_price,
                'Keepa Used Is FBA': buybox_used_is_fba,
            }
        return prices
    except Exception as e:
        print(f"Error getting Keepa prices: {e}")
        return {}


def send_telegram_message(chat_id, text):
    try:
        token = os.getenv('telegram_token')
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': text
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
        print(f"Error deleting Telegram message: {e}")
        return None

@load_json_body
def lambda_handler(event, context):
    try:
        print(event)
        chat_id = event['chat_id']

        creds = authenticate_gmail()
        if not creds:
            raise Exception("Failed to authenticate Gmail")
        
        seller_client = SellerClient(client_id=os.getenv('client_id'),client_secret=os.getenv('client_secret'),refresh_token=os.getenv('refresh_token'),seller_id=os.getenv('merchant_token'))
        
        service = build('gmail', 'v1', credentials=creds)
        emails = get_emails_with_subject(service, 'NEW!', 1)
 

        sellable_products = []
        for email in emails:
            asin = email['ASIN']
            restrictions = seller_client.check_listing_restrictions(asin=asin)
            if restrictions and not restrictions.get('restrictions'):
                sellable_products.append(email)
        
        asins = [email['ASIN'] for email in sellable_products]
        keepa_prices = get_keepa_prices(asins)
        client = boto3.client('lambda')
        function_name = os.getenv('process_ebay_function')
        
        for email in sellable_products:
            link = parse_html(email['Html'])
            email['ebay_link'] = link
            del email['Html']

            if link:
                keepa_price = keepa_prices.get(email['ASIN'], {})
                email.update(keepa_price)
                email['chat_id'] = chat_id
                client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',
                    Payload=json.dumps(email)
                )
    
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Emails processed and function invoked'})
        }

    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        send_telegram_message(chat_id, "An error occurred while processing emails.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
if __name__ == '__main__':
    lambda_handler({},{})