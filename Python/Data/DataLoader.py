import requests
import json
import hashlib
from datetime import datetime, timezone
import os
import pandas as pd

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

# Load stock codes from CSV
def load_stock_codes_from_csv(csv_file_path="stock_names_symbol.csv", start_index=0, end_index=None):
    """
    Load stock codes from CSV file
    
    Args:
        csv_file_path: Path to the CSV file
        start_index: Starting index (0-based)
        end_index: Ending index (None for all remaining)
    
    Returns:
        List of stock symbols
    """
    try:
        # Read the CSV file without headers
        df = pd.read_csv(csv_file_path, header=None)
        
        # Get the stock symbols from the second column (index 1)
        stock_symbols = df[1].tolist()
        
        # Slice based on start and end index
        if end_index is None:
            selected_stocks = stock_symbols[start_index:]
        else:
            selected_stocks = stock_symbols[start_index:end_index + 1]
        
        print(f"📊 Loaded {len(selected_stocks)} stock codes from CSV")
        print(f"   Range: Index {start_index} to {end_index if end_index else len(stock_symbols)-1}")
        print(f"   Sample stocks: {selected_stocks[:5]}...")
        
        return selected_stocks
    
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file_path}")
        return []
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return []

# Function to fetch data for a single stock
def fetch_historical_data(stock_code, session_token):
    """Fetch historical data for a single stock"""
    print(f"\n📈 Fetching data for: {stock_code}")
    
    # Update timestamp for each request
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    # Payload for historical data
    payload = json.dumps({
        "interval": "30minute",
        "from_date": "2025-10-01T09:20:00.000Z", 
        "to_date": "2025-10-01T15:30:00.000Z",
        "stock_code": stock_code,
        "exchange_code": "NSE",
        "product_type": "futures"
    }, separators=(',', ':'))
    
    # Generate checksum
    checksum = hashlib.sha256((time_stamp + payload + secret_key).encode("utf-8")).hexdigest()
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Checksum': 'token ' + checksum,
        'X-Timestamp': time_stamp,
        'X-AppKey': appkey,
        'X-SessionToken': session_token
    }
    
    # Make request
    try:
        response = requests.request("GET", historical_url, headers=headers, data=payload)
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Check ICICI API specific error structure
            if isinstance(response_data, dict):
                # Check if there's an actual error (Error field is not None)
                if response_data.get("Error") is not None:
                    print(f"❌ API Error for {stock_code}")
                    print(f"   Error: {response_data.get('Error')}")
                    return {"error": "API Error", "response": response_data.get('Error')}
                
                # Check if Success field exists and has data
                if "Success" in response_data:
                    success_data = response_data["Success"]
                    if not success_data or (isinstance(success_data, list) and len(success_data) == 0):
                        print(f"❌ No data found for {stock_code}")
                        print(f"   Success field is empty")
                        return {"error": "No data found", "response": "Success field is empty"}
                else:
                    print(f"❌ Invalid response structure for {stock_code}")
                    print(f"   Response: {response_data}")
                    return {"error": "Invalid response structure", "response": response_data}
            
            # Check if response is completely empty
            if not response_data:
                print(f"❌ Empty response for {stock_code}")
                return {"error": "Empty response", "response": response_data}
            
            print(f"✓ Success for {stock_code}")
            return response_data
        else:
            print(f"❌ HTTP Error for {stock_code}: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return {"error": f"HTTP {response.status_code}", "response": response.text[:200]}
            
    except Exception as e:
        print(f"❌ Exception for {stock_code}: {e}")
        return {"error": "Exception", "response": str(e)}

# Load stock codes from CSV
# You can modify these parameters:
START_INDEX = 11      # Start from first stock (0-based)
END_INDEX = 13       # End at 10th stock (set to None for all stocks)

stock_codes = load_stock_codes_from_csv(
    csv_file_path="stock_names_symbol.csv",
    start_index=START_INDEX,
    end_index=END_INDEX
)

if not stock_codes:
    print("❌ No stock codes loaded. Exiting...")
    exit(1)

# Dictionary to store all results
all_data = {}
failed_stocks = []  # List to track failed stocks with details
successful_requests = 0
failed_requests = 0

print(f"\n🚀 Starting data fetch for {len(stock_codes)} stocks...")
print("="*60)

# Iterate through stock codes
for i, stock_code in enumerate(stock_codes, 1):
    print(f"\n[{i}/{len(stock_codes)}] Processing: {stock_code}")
    
    # Fetch data for this stock
    data = fetch_historical_data(stock_code, session_token)
    
    if data and "error" not in data:
        # Only save if we have valid data (no errors)
        all_data[stock_code] = data
        successful_requests += 1
        
        # Save individual file
        filename = f'test_folder/data_{stock_code}_5min.json'
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"   ✓ Saved to {filename}")
        except Exception as e:
            print(f"   ❌ Failed to save {filename}: {e}")
    else:
        # Log as failed request
        failed_requests += 1
        
        # Record failed stock with details
        failed_entry = {
            "stock_code": stock_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": data.get("error", "Unknown error") if data else "No response",
            "response": data.get("response", "No response data") if data else "No response"
        }
        failed_stocks.append(failed_entry)
        print(f"   ❌ Logged as failed request")
    
    # Add a small delay to avoid rate limiting
    import time
    time.sleep(0.5)  # 500ms delay between requests

# Save combined data
print("\n" + "="*60)
print("📊 SUMMARY")
print("="*60)
print(f"Total stocks processed: {len(stock_codes)}")
print(f"Successful requests: {successful_requests}")
print(f"Failed requests: {failed_requests}")
print(f"Success rate: {(successful_requests/len(stock_codes)*100):.1f}%")

# Save combined results
if all_data:
    combined_filename = f'test_folder/icici_historical_data_combined_{START_INDEX}_to_{END_INDEX}.json'
    try:
        with open(combined_filename, 'w') as f:
            json.dump(all_data, f, indent=2)
        print(f"\n✓ Combined data saved to '{combined_filename}'")
        print(f"   Contains data for {len(all_data)} stocks")
    except Exception as e:
        print(f"\n❌ Failed to save combined data: {e}")

# Save failed stocks record
if failed_stocks:
    failed_txt_filename = f'test_folder/failed_stocks_{START_INDEX}_to_{END_INDEX}.txt'
    try:
        with open(failed_txt_filename, 'w') as f:
            f.write(f"Failed Stock Codes ({len(failed_stocks)} total):\n")
            f.write("=" * 50 + "\n\n")
            for entry in failed_stocks:
                f.write(f"Stock: {entry['stock_code']}\n")
                f.write(f"Error: {entry['error_type']}\n")
                f.write(f"Time: {entry['timestamp']}\n")
                f.write("-" * 30 + "\n")
        print(f"\n📝 Failed stocks list saved to '{failed_txt_filename}'")
        print(f"   Contains {len(failed_stocks)} failed requests")
        
    except Exception as e:
        print(f"\n❌ Failed to save failed stocks log: {e}")

print(f"\n🎉 Process completed!")