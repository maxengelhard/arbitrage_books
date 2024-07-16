import os
import requests
import pandas as pd
from bs4 import BeautifulSoup

def search(page_num):
    url = "https://essearchapi-na.hawksearch.com/api/v2/search/"

    payload = f'{{"Keyword":"","FacetSelections":{{}},"MaxPerPage":"96","PageNo":{page_num},"SortBy":"date-asc","ClientGuid":"5c745d1ab1084b97b1ece8743ff8eda5","IndexName":"uscollege.20240606.163434.uscollegeprod","ClientData":{{"VisitorId":"219388d1-3598-4036-8973-9871fd0f3737"}}}}'
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://collegepublishing.sagepub.com',
        'priority': 'u=1, i',
        'referer': 'https://collegepublishing.sagepub.com/',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    response_json = response.json()
    results = response_json['Results']
    return results

def scrape_page(page_url):
    url = f"https://collegepublishing.sagepub.com{page_url}"
    print(f"Scraping {url}")

    payload = {}
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all elements with data-value="1"
        prices = []
        elements = soup.find_all(attrs={"data-value": "1"})
        
        for element in elements:
            price_text = element.text.strip().replace('$', '')
            try:
                price = float(price_text)
                prices.append(price)
            except ValueError:
                continue
        
        if prices:
            return min(prices)
        else:
            return None

def save_to_csv(data, filename='product_prices.csv'):
    file_exists = os.path.isfile(filename)
    if file_exists:
        existing_df = pd.read_csv(filename)
        df = pd.DataFrame(data)
        combined_df = pd.concat([existing_df, df]).drop_duplicates().sort_values(by='min_price')
    else:
        combined_df = pd.DataFrame(data).sort_values(by='min_price')

    combined_df.to_csv(filename, index=False)
    print(combined_df)

def main():
    for i in range(4,133):  # Adjust the range as needed
        results = search(i)
        for result in results:
            document = result['Document']
            page_url = document.get('pageurl')[0]
            title = document.get('title')[0]
            product_formats = document.get('productformats')
            
            if page_url and product_formats and 'Print' in product_formats:
                min_price = scrape_page(page_url)
                print(min_price)
                if min_price is not None:
                    result_data = [{
                        'title': title,
                        'page_url': page_url,
                        'min_price': min_price
                    }]
                    save_to_csv(result_data)

if __name__ == "__main__":
    main()
