import requests
from dotenv import load_dotenv
load_dotenv()
import os
from enum import Enum

class SellerClient:
    # Define the ConditionType enum
    class ConditionType(Enum):
        NEW_NEW = "new_new"

    def __init__(self) -> None:
        self.client_id = os.getenv('client_id')
        self.client_secret = os.getenv('client_secret')
        self.refresh_token = os.getenv('refresh_token')
        self.seller_id = os.getenv('merchant_token')
        self.marketplace_ids = 'ATVPDKIKX0DER'
        self.access_token = self.get_access_token()
        self.condition = self.ConditionType.NEW_NEW
        if self.access_token is None:
            raise Exception("Failed to obtain access token.")

    
    # Function to get the access token
    def get_access_token(self):
        token_url = "https://api.amazon.com/auth/o2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            tokens = response.json()
            return tokens['access_token']
        else:
            print("Error obtaining access token:", response.text)
            return None


    def check_listing_restrictions(self, asin):
        url=f"https://sellingpartnerapi-na.amazon.com/listings/2021-08-01/restrictions"
        params = {
            "asin": asin,
            "sellerId": self.seller_id,
            "marketplaceIds": self.marketplace_ids,
            "conditionType": self.condition.value
        }
        headers = {
            "x-amz-access-token": self.access_token,
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print("Error checking listing restrictions:", response.text)
            return None


if __name__ == '__main__':
   seller_client = SellerClient()
   restritions = seller_client.check_listing_restrictions(asin='032379341X')
   print(restritions)


