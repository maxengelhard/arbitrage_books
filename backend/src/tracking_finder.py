import asyncio
import keepa
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import os

async def main():
    key = os.getenv('keepa_api')
    api = await keepa.AsyncKeepa().create(key)

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
        product_params = {
            'rootCategory': 283155, # for books
            'isAdultProduct': False, # do not want this
            'current_NEW_FBA_gte': 6000,# new prices greater than $60
            'avg90_SALES_gte' : 25000, # sales rank greater than 25000
            'avg90_SALES_lte': 150000, # sales rank lower than 150000
            'current_SALES_gte': current_sales_gte,
            'current_SALES_lte' : max_sales_lte,
            'stockAmazon_lte' : 1,
            'offerCountFBA_gte': 5,
            'sort': ["current_SALES", "asc"],
        }
        products = await api.product_finder(product_parms=product_params, domain='US')
        if not products:
            break
        last_product_asin = products[-1]
        if last_product_asin == current_product_asin:
            break
        current_product_asin = last_product_asin
        last_product= await api.query(items=last_product_asin,days=1,stats=1)
        current_sales_gte = last_product[0]['stats']['current'][3]
        
        print(current_sales_gte)
        
        df = pd.DataFrame(products, columns=['ASIN'])
        df.to_csv(csv_file, mode='a', header=False, index=False)


if __name__ == '__main__':
    asyncio.run(main())
