import os.path
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

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

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
                    asin = subject_line.split(':')[0] 
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
        headers = ['ASIN', 'Date', 'ebay_link', 'Ebay: Lowest Pre-Owned Price', 'Ebay: Lowest New Price', 'amz_link', 'Keepa New Price (FBA)', 'Keepa Used Price (FBA)']
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
    api = keepa.Keepa(os.environ.get('keepa_api'))
    products = api.query(asins, only_live_offers=1, days=1,offers=100)
    prices = {}

    for product in products:
        asin = product['asin']
        fba_new_prices = []
        fba_used_prices = []
        
        for offer in product['offers']:
            price_cents = offer['offerCSV'][1]
            price = price_cents / 100
            if offer['isFBA']:
                if offer['condition'] == 1:  # 1 is for New condition
                    fba_new_prices.append(price)
                elif offer['condition'] != 1:  # 2 is for Used condition
                    fba_used_prices.append(price)
        
        min_new_price = min(fba_new_prices) if fba_new_prices else None
        min_used_price = min(fba_used_prices) if fba_used_prices else None
        
        prices[asin] = {
            'Keepa New Price (FBA)': min_new_price,
            'Keepa Used Price (FBA)': min_used_price
        }
    return prices

def main():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    
    emails = get_emails_with_subject(service, 'NEW!', 7)

    asins = [email['ASIN'] for email in emails]

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
        if (lowest_pre_owned and keepa_price.get('Keepa Used Price (FBA)') and lowest_pre_owned <= keepa_price.get('Keepa Used Price (FBA)') *.6) or \
           (lowest_new and keepa_price.get('Keepa New Price (FBA)') and lowest_new <= keepa_price.get('Keepa New Price (FBA)') * .6):
            filtered_emails.append(email)

    save_to_csv(filtered_emails)

if __name__ == '__main__':
    main()
