import os
import json
import requests
from bs4 import BeautifulSoup
import prettytable as pt

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

    lowest_pre_owned = round(min(pre_owned_prices), 2) if pre_owned_prices else None
    lowest_new = round(min(new_prices), 2) if new_prices else None

    return lowest_pre_owned, lowest_new

def send_telegram_message(message, inline_buttons, chat_id):
    token = os.getenv('telegram_token')
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps({
            'inline_keyboard': inline_buttons
        })
    }
    response = requests.post(url, data=payload)
    return response.json()

def lambda_handler(event, context):
    print(event)
    body = event['body']
    email = body
    link = email['ebay_link']
    chat_id = email['chat_id']
    if link:
        lowest_pre_owned, lowest_new = scrape_ebay_page(link)
        email['Ebay: Lowest Pre-Owned Price'] = lowest_pre_owned
        email['Ebay: Lowest New Price'] = lowest_new

        used_col = email['Ebay: Lowest Pre-Owned Price'] is not None and email['Max Used Price'] is not None and email['Ebay: Lowest Pre-Owned Price'] <= email['Max Used Price']
        new_col = email['Ebay: Lowest New Price'] is not None and email['Max New Price'] is not None and email['Ebay: Lowest New Price'] <= email['Max New Price']

        table = pt.PrettyTable()
        table.align = 'l'
        table.field_names = ['Item', 'Used', 'New']

        if used_col:
            table.add_row(['eBay', f"${email['Ebay: Lowest Pre-Owned Price']}", ''])
            table.add_row(['Max Price', f"${email['Max Used Price']}", ''])
            table.add_row(['Amazon', f"${email['Keepa Used Price']}", ''])
            table.add_row(['FBA', f"{email['Keepa Used Is FBA']}", ''])

        if new_col:
            if not used_col:
                table.add_row(['eBay', '', f"${email['Ebay: Lowest New Price']}"])
                table.add_row(['Max Price', '', f"${email['Max New Price']}"])
                table.add_row(['Amazon', '', f"${email['Keepa New Price']}"])
                table.add_row(['FBA', '', f"{email['Keepa New Is FBA']}"])
            else:
                table._rows[0][2] = f"${email['Ebay: Lowest New Price']}"
                table._rows[1][2] = f"${email['Max New Price']}"
                table._rows[2][2] = f"${email['Keepa New Price']}"
                table._rows[3][2] = f"{email['Keepa New Is FBA']}"

        if new_col or used_col:
            message = f"""
            <b>Title:</b> {email['Title']}
            <pre>{table}</pre>
            """
            inline_buttons = [
                [
                    {"text": "View on eBay", "url": email['ebay_link']},
                    {"text": "View on Amazon", "url": email['amz_link']}
                ],
                [
                    {"text": "Delete", "callback_data": f"delete_{email['ASIN']}"}
                ]
            ]
            send_telegram_message(message, inline_buttons, chat_id)

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'eBay page scraped and Telegram message sent'})
    }

if __name__ == '__main__':
    lambda_handler({}, {})
