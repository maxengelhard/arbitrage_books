import asyncio
import keepa
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import os
from amazon_seller_check import SellerClient

def main():
    key = os.getenv('keepa_api')
    api = keepa.Keepa(key)
    seller_client = SellerClient(client_id=os.getenv('client_id'),client_secret=os.getenv('client_secret'),refresh_token=os.getenv('refresh_token'),seller_id=os.getenv('merchant_token'))

    current_product_asin = None
    current_sales_gte = 25000
    max_sales_lte = 150000
    
    csv_file = 'products.csv'
    with open(csv_file, 'w') as f:
        f.write('ASIN\n')

    while current_sales_gte <= max_sales_lte:
        # categories = await api.category_lookup(0)
        # for cat_id in categories:
        #     print(cat_id, categories[cat_id]['name'])
        # return categories
        product_params=  {
        "avg90_SALES_gte": 10000,
        "avg90_SALES_lte": 150000,
        "current_BUY_BOX_SHIPPING_gte": 5000,
        "buyBoxStatsAmazon30_gte": 0,
        "buyBoxStatsAmazon30_lte": 50,
        "current_AMAZON_gte": -1,
        "current_AMAZON_lte": -1,
        "current_NEW_gte": 5000,
        "current_NEW_FBA_gte": 5000,
        "current_COUNT_NEW_gte": 2,
        "rootCategory": 283155,
        "sort": [
            [
                "current_SALES",
                "asc"
            ]
        ],
        "lastOffersUpdate_gte": 7122131,
        # "productType": [
        #     0,
        #     1,
        #     2
        # ],
        # "perPage": 50,
        # "page": 0
        }   
        products = api.product_finder(product_parms=product_params, domain='US')
        if not products:
            break
        last_product_asin = products[-1]
        if last_product_asin == current_product_asin:
            break
        current_product_asin = last_product_asin
        last_product= api.query(items=last_product_asin,days=1,stats=1)
        current_sales_gte = last_product[0]['stats']['current'][3]
        
        sellable_products = []
        for product in products:
            restrictions = seller_client.check_listing_restrictions(asin=product)
            if restrictions and not restrictions.get('restrictions'):
                sellable_products.append(product)
        
        df = pd.DataFrame(sellable_products, columns=['ASIN'])
        df.to_csv(csv_file, mode='a', header=False, index=False)


if __name__ == '__main__':
    main()
