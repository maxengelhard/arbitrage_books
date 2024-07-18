import asyncio
import keepa
from dotenv import load_dotenv
load_dotenv()
import os

async def main():
    key = os.getenv('keepa_api')
    api = await keepa.AsyncKeepa().create(key)
    # categories = await api.category_lookup(0)
    # for cat_id in categories:
    #     print(cat_id, categories[cat_id]['name'])
    # return categories
    product_params = {
        'rootCategory': 283155, # for books
        'isAdultProduct': False, # do not want this
        'current_NEW_FBA_gte': 8000,# new prices greater than $40
        'avg90_SALES_gte' : 25000, # sales rank greater than 25000
        'avg90_SALES_lte': 150000, # sales rank lower than 150000
        'current_SALES_gte': 25000,
        'current_SALES_lte' : 150000,
        'stockAmazon_lte' : 1,
        'offerCountFBA_gte': 5,
        'sort': ["current_SALES", "asc"],
    }
    products = await api.product_finder(product_parms=product_params, domain='US')
    print(products)
    last_product= await api.query(items='032381025X',days=1,stats=1)
    current_sales_rank = last_product[0]['stats']['current'][3]
    print(current_sales_rank)


if __name__ == '__main__':
    asyncio.run(main())
