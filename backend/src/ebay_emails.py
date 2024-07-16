import os.path
import boto3
import re
import datetime
import base64
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import requests
import keepa
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
            key = 'credentials.json'
            credentials_json = get_secret_from_s3(bucket_name, key)
            with open('token.json', 'w') as creds_file:
                creds_file.write(credentials_json)
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
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

def save_to_csv(data, filename='filtered_emails.csv'):
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by='Date')
        # Ensure the headers are in the specified order
        headers = ['ASIN', 'Date', 'ebay_link', 'amz_link', 'Ebay: Lowest Pre-Owned Price','Max Used Price','Keepa Used Price','Keepa Used Is FBA', 'Ebay: Lowest New Price' ,'Max New Price', 'Keepa New Price', 'Keepa New Is FBA']
        df = df[headers]
        df.to_csv(filename, index=False)
    print(df)

def scrape_ebay_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    pre_owned_prices = []
    new_prices = []

    results_div = soup.find('div', class_='srp-river-results')
    if not results_div:
        return None, None
    
    listings = results_div.select('.s-item__info')
    for listing in listings:
        if listing.find('span', class_='s-item__formatBuyItNow'):
            condition = listing.select_one('.SECONDARY_INFO').text if listing.select_one('.SECONDARY_INFO') else ''
            price_text = listing.select_one('.s-item__price').text.strip().replace('$', '').replace(',', '')
            shipping_text = listing.select_one('.s-item__shipping').text if listing.select_one('.s-item__shipping') else ''
            try:
                price = float(price_text)
                if 'Free shipping' not in shipping_text:
                    shipping_cost = float(shipping_text.strip().replace(' shipping', '').replace('+$', '').replace(',', ''))
                    price += shipping_cost
                if 'Pre-Owned' in condition:
                    pre_owned_prices.append(price)
                elif 'Brand New' in condition:
                    new_prices.append(price)
            except ValueError:
                continue

    lowest_pre_owned = min(pre_owned_prices) if pre_owned_prices else None
    lowest_new = min(new_prices) if new_prices else None

    return lowest_pre_owned, lowest_new

def get_keepa_prices(asins):
    api = keepa.Keepa(accesskey=os.getenv('keepa_api'),timeout=300)
    products = api.query(asins, only_live_offers=1, days=1,stats=180,buybox=1) # offers=20
    prices = {}

    for product in products:
        asin = product['asin']

        stats = product.get('stats',{})
        buybox_new_price = stats.get('buyBoxPrice', None)
        buybox_new_shipping = stats.get('buyBoxShipping', None)
        buybox_new_is_fba = stats.get('buyBoxIsFBA', None)
        
        buybox_used_price = stats.get('buyBoxUsedPrice', None)
        buybox_used_shipping = stats.get('buyBoxUsedShipping', None)
        buybox_used_is_fba = stats.get('buyBoxUsedIsFBA', None)
        
        
        new_price = float(buybox_new_price + buybox_new_shipping)/100 if buybox_new_price else None
        used_price = float(buybox_used_price + buybox_used_shipping)/100 if buybox_used_price else None
        
        prices[asin] = {
            'Keepa New Price': new_price,
            'Max New Price': new_price * .6,
            'Keepa New Is FBA': buybox_new_is_fba,
            'Keepa Used Price': used_price,
            'Max Used Price': used_price * .6,
            'Keepa Used Is FBA': buybox_used_is_fba,
        }
    return prices

def lambda_handler(event,context):
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    
    emails = get_emails_with_subject(service, 'NEW!', 1)

    asins = [email['ASIN'] for email in emails ]
    keepa_prices = get_keepa_prices(asins)
    filtered_emails = []

    for email in emails:
        link = parse_html(email['Html'])
        email['ebay_link'] = link
        del email['Html']

        if link:
            lowest_pre_owned, lowest_new = scrape_ebay_page(link)
            email['Ebay: Lowest Pre-Owned Price'] = lowest_pre_owned
            email['Ebay: Lowest New Price'] = lowest_new

        keepa_price = keepa_prices.get(email['ASIN'], {})
        email.update(keepa_price)

        # Filter condition: eBay price must be half of the FBA price
        if (lowest_pre_owned and keepa_price.get('Keepa Used Price') and lowest_pre_owned <= keepa_price.get('Max Used Price')) or \
           (lowest_new and keepa_price.get('Keepa New Price') and lowest_new <= keepa_price.get('Max New Price')):
            filtered_emails.append(email)


    save_to_csv(filtered_emails)

if __name__ == '__main__':
    main()
