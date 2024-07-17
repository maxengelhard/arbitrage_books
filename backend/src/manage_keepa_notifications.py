import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get('keepa_api')

# Base URL for Keepa API
KEEPA_API_URL = 'https://api.keepa.com/tracking'

# Function to add a new product tracking
def add_tracking(tracking_object):
    url = f'{KEEPA_API_URL}?key={API_KEY}&type=add'
    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.post(url, headers=headers, data=json.dumps(tracking_object))
    return response

# Example usage
# Example tracking objects
tracking_objects = [
    {
        "asin": "0262048647",  # Example ASIN
        "ttl": 0,  # Never expires
        "expireNotify": True,
        "desiredPricesInMainCurrency": True,
        "mainDomainId": 1,  # Amazon US
        "updateInterval": 24,  # Update every 24 hours
        "metaData": "Tracking new and used prices on amazon and ebay",
        "thresholdValues": [
            {
                "thresholdValue": 10000,  # Desired new price in cents (i.e., $100.00)
                "domain": 1,  # Amazon US
                "csvType": 0,  # New price type
                "isDrop": True  # Track price drops
            },
            {
                "thresholdValue": 20000,  # Desired used price in cents (i.e., $20.00)
                "domain": 1,  # Amazon US
                "csvType": 1,  # Used price type
                "isDrop": True  # Track price drops
            },
            {
                "thresholdValue": 20000,  # Desired used price in cents (i.e., $20.00)
                "domain": 1,  # Amazon US
                "csvType": 28,  # Ebay new plus shipping
                "isDrop": True  # Track price drops
            },
            {
                "thresholdValue": 20000,  # Desired used price in cents (i.e., $20.00)
                "domain": 1,  # Amazon US
                "csvType": 29,  # Ebay Used plus shipping
                "isDrop": True  # Track price drops
            },

        ],
        "notificationType": [False, False, False, False, False, True, False],  # Only notify via API
        "individualNotificationInterval": -1  # Use default notification timer
    }
]

# response = add_tracking(tracking_objects)
# print(response.status_code)
# print(response.json())
  



# Convert a datetime to KeepaTime minutes
def to_keepa_time(dt):
    unix_epoch = datetime(1970, 1, 1)
    keepa_epoch = datetime(2009, 1, 1)
    delta = (dt - unix_epoch).total_seconds() // 60
    return int((delta - 21564000) / 60)

# Function to get notifications
def get_notifications(since, revise=False):
    keepa_time_since = to_keepa_time(since)
    revise_value = 1 if revise else 0
    url = f'{KEEPA_API_URL}?key={API_KEY}&type=notification&since={keepa_time_since}&revise={revise_value}'
    response = requests.get(url)
    return response

# Example usage
since_date = datetime.now() - timedelta(days=1)  # Get notifications from the last 24 hours
revise = False  # Do not request notifications already marked as read

response = get_notifications(since_date, revise)
print(response.status_code)
print(response.json())
