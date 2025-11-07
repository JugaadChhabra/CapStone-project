import requests
import json
import hashlib
from datetime import datetime, timezone

load.dotenv()

customerDetail_url = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
secret_key = os.getenv('ICICI_SECRET_KEY')
appkey = os.getenv('ICICI_APP_KEY')
session_key = os.getenv('ICICI_SESSION_KEY')
time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'

customerDetail_payload = json.dumps({
  "SessionToken": session_key,
  "AppKey": appkey
})

customerDetail_headers = {
    'Content-Type': 'application/json',
}

customerDetail_response = requests.request("GET", customerDetail_url, headers=customerDetail_headers, data=customerDetail_payload)
data = json.loads(customerDetail_response.text)
session_token = data["Success"]["session_token"]

url = "https://api.icicidirect.com/breezeapi/api/v1/order"

payload = json.dumps({
  "stock_code": "NIFTY",
  "exchange_code": "NFO",
  "product": "options",
  "action": "buy",
  "order_type": "limit",
  "quantity": "25",
  "price": "1",
  "validity": "day",
  "stoploss": "",
  "validity_date": "2024-07-23T06:00:00.000Z",
  "disclosed_quantity": "0",
  "expiry_date": "2024-09-12T06:00:00.000Z",
  "right": "call",
  "strike_price": "25000",
  "user_remark": "testing" 
  }, separators=(',', ':'))

checksum = hashlib.sha256((time_stamp+payload+secret_key).encode("utf-8")).hexdigest()
headers = {
    'Content-Type': 'application/json',
    'X-Checksum': 'token '+ checksum,
    'X-Timestamp': time_stamp,
    'X-AppKey': appkey,
    'X-SessionToken': session_token
}

response = requests.request("POST", url, headers=headers, data=payload)
print(response.text)
