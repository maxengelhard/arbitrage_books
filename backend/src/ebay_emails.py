import os.path
import boto3
import re
import datetime
import json
import base64
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import requests
import keepa
import prettytable as pt
# from telegram import ParseMode
from dotenv import load_dotenv
load_dotenv()

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_secret_from_s3(bucket_name, key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket_name, Key=key)
    return response['Body'].read().decode('utf-8')

def upload_secret_to_s3(bucket_name, key, data):
    s3 = boto3.client('s3')
    s3.put_object(Bucket=bucket_name, Key=key, Body=data)

def authenticate_gmail():
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

def extract_asin(subject_line):
    # Split the subject line by ':' or ','
    parts = re.split('[:,]', subject_line)
    
    # Extract the first part
    asin = parts[0].strip()
    
    # Check if the ASIN contains only numbers
    if asin.isdigit():
        return asin[-10:]
    else:
        return None

def get_emails_with_subject(service, subject, days):
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

def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    h1_tag = soup.find('h1')
    if h1_tag:
        a_tag = h1_tag.find('a')
        if a_tag and 'href' in a_tag.attrs:
            return a_tag['href']
    return None


def get_keepa_prices(asins):
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

        max_new_price = round(new_price * .6,2) if new_price else None
        max_used_price = round(used_price * .6,2) if used_price else None
        
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

def send_telegram_message(chat_id, text):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    requests.post(url, data=payload)

def delete_telegram_message(chat_id, message_id):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/deleteMessage'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    response = requests.post(url, data=payload)
    return response.json()

def lambda_handler(event, context):
    body = json.loads(event['body'])
    
    if 'message' in body:
        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        if text == '/ebay':
            start_response = send_telegram_message(chat_id, "The eBay data gathering process has started.")
            start_message_id = start_response['result']['message_id']

            creds = authenticate_gmail()
            service = build('gmail', 'v1', credentials=creds)
            emails = get_emails_with_subject(service, 'NEW!', 1)
            asins = [email['ASIN'] for email in emails]
            keepa_prices = get_keepa_prices(asins)
            
            sqs = boto3.client('sqs')
            queue_url = os.getenv('SQS_QUEUE_URL')
            
            for email in emails:
                link = parse_html(email['Html'])
                email['ebay_link'] = link
                del email['Html']

                if link:
                    keepa_price = keepa_prices.get(email['ASIN'], {})
                    email.update(keepa_price)
                    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(email))
            
            delete_telegram_message(chat_id, start_message_id)

    return {
        'status': 200,
        'message': 'Emails processed and messages sent to SQS'
    }

if __name__ == '__main__':
    lambda_handler({},{})