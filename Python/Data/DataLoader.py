import requests
import json
import hashlib
from datetime import datetime, timezone
import os

# API Configuration
customerDetail_url = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
historical_url = "https://api.icicidirect.com/breezeapi/api/v1/historicalcharts"

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Credentials - Replace with your actual keys
secret_key = os.getenv("SECRET_KEY")
appkey = os.getenv("APP_KEY") 
session_key = os.getenv("API_SESSION_TOKEN")

# Debug: Check if environment variables are loaded
print("🔐 Environment Variables Check:")
print(f"SECRET_KEY: {'✓ Loaded' if secret_key else '❌ Missing'}")
print(f"APP_KEY: {'✓ Loaded' if appkey else '❌ Missing'}")  
print(f"SESSION_KEY: {'✓ Loaded' if session_key else '❌ Missing'}")
print()

if not all([secret_key, appkey, session_key]):
    print("❌ Missing required environment variables. Please check your .env file.")
    print("Required variables: SECRET_KEY, APP_KEY, SESSION_KEY")
    exit(1)

# Step 1: Get Session Token
print("Fetching session token...")
time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'

customerDetail_payload = json.dumps({
    "SessionToken": session_key,
    "AppKey": appkey
})

customerDetail_headers = {
    'Content-Type': 'application/json',
}

customerDetail_response = requests.request("GET", customerDetail_url, 
                                          headers=customerDetail_headers, 
                                          data=customerDetail_payload)

print(f"Response Status Code: {customerDetail_response.status_code}")
print(f"Response Text: {customerDetail_response.text}")

try:
    data = json.loads(customerDetail_response.text)
    print(f"Parsed Data: {data}")
    
    if data and "Success" in data and "session_token" in data["Success"]:
        session_token = data["Success"]["session_token"]
        print(f"Session token retrieved: {session_token[:20]}...")
    else:
        print("❌ Error: Could not find session token in response")
        print(f"Available keys in response: {list(data.keys()) if data else 'None'}")
        if data and "Error" in data:
            print(f"API Error: {data['Error']}")
        exit(1)
        
except json.JSONDecodeError as e:
    print(f"❌ JSON Decode Error: {e}")
    print(f"Raw response: {customerDetail_response.text}")
    exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    exit(1)

# Step 2: Fetch Historical Data (5-minute intervals)
print("\nFetching 5-minute interval data from April 1 to October 1, 2025...")

# Update timestamp for the second request
time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'

# Payload for 5-minute interval data
payload = json.dumps({
    "interval": "5minute",
    "from_date": "2025-04-01T09:20:00.000Z",  # April 1, 2025 (market opening)
    "to_date": "2025-10-01T15:30:00.000Z",    # October 1, 2025 (market closing)
    "stock_code": "NIFTY",
    "exchange_code": "NSE",
    "product_type": "futures"
}, separators=(',', ':'))

# Generate checksum
checksum = hashlib.sha256((time_stamp + payload + secret_key).encode("utf-8")).hexdigest()

# Headers for historical data request
headers = {
    'Content-Type': 'application/json',
    'X-Checksum': 'token ' + checksum,
    'X-Timestamp': time_stamp,
    'X-AppKey': appkey,
    'X-SessionToken': session_token
}

# Make the request
response = requests.request("GET", historical_url, headers=headers, data=payload)

# Print response
print("\n" + "="*60)
print("API Response:")
print("="*60)
print(response.text)

# Optional: Save to file
try:
    response_data = json.loads(response.text)
    with open('icici_historical_data_5min.json', 'w') as f:
        json.dump(response_data, f, indent=2)
    print("\n✓ Data saved to 'icici_historical_data_5min.json'")
except:
    print("\n✗ Could not parse/save response as JSON")