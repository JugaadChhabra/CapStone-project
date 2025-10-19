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

# Function to get session token (reusable)
def get_session_token():
    """Get session token from ICICI API"""
    
    print("🔐 Getting session token...")
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    customerDetail_payload = json.dumps({
        "SessionToken": session_key,
        "AppKey": appkey
    })
    
    customerDetail_headers = {
        'Content-Type': 'application/json',
    }
    
    try:
        customerDetail_response = requests.request("GET", customerDetail_url, 
                                                  headers=customerDetail_headers, 
                                                  data=customerDetail_payload)
        
        data = json.loads(customerDetail_response.text)
        
        if data and "Success" in data and "session_token" in data["Success"]:
            session_token = data["Success"]["session_token"]
            print(f"✅ Session token obtained: {session_token[:20]}...")
            return session_token
        else:
            print("❌ Error: Could not find session token in response")
            if data and "Error" in data:
                print(f"   API Error: {data['Error']}")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

# Get session token when module is imported (for backward compatibility)
print("Fetching session token...")
session_token = get_session_token()

if not session_token:
    print("❌ Could not get session token. Some functions may not work.")
else:
    print(f"Session token retrieved: {session_token[:20]}...")

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
    
    # Update timestamp for each request
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    # Payload for historical data
    payload = json.dumps({
        "interval": "5minute",
        "from_date": "2025-10-17T09:10:00.000Z", 
        "to_date": "2025-10-17T09:30:00.000Z",
        "stock_code": stock_code,
        "exchange_code": "NSE",
        "product_type": "cash"
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
                    return {"error": "API Error", "response": response_data.get('Error')}
                
                # Check if Success field exists and has data
                if "Success" in response_data:
                    success_data = response_data["Success"]
                    if not success_data or (isinstance(success_data, list) and len(success_data) == 0):
                        return {"error": "No data found", "response": "Success field is empty"}
                else:
                    return {"error": "Invalid response structure", "response": response_data}
            
            # Check if response is completely empty
            if not response_data:
                return {"error": "Empty response", "response": response_data}
            
            return response_data
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text[:200]}
            
    except Exception as e:
        return {"error": "Exception", "response": str(e)}

# Function to fetch previous day closing prices (separate utility)
def fetch_previous_day_close(stock_code, session_token, target_date="2025-10-16"):
    """
    Fetch previous day closing price for a single stock
    
    Args:
        stock_code: Stock symbol
        session_token: API session token
        target_date: Date for which to fetch closing price (YYYY-MM-DD)
    
    Returns:
        Dict with closing price data or error info
    """
    
    # Update timestamp for each request
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    # Payload for previous day data (daily interval to get closing price)
    payload = json.dumps({
        "interval": "day",
        "from_date": f"{target_date}T00:00:00.000Z", 
        "to_date": f"{target_date}T23:59:59.000Z",
        "stock_code": stock_code,
        "exchange_code": "NSE",
        "product_type": "cash"
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
    
    try:
        response = requests.request("GET", historical_url, headers=headers, data=payload)
        
        if response.status_code == 200:
            response_data = response.json()
            
            if isinstance(response_data, dict):
                if response_data.get("Error") is not None:
                    return {"error": "API Error", "response": response_data.get('Error')}
                
                if "Success" in response_data and response_data["Success"]:
                    success_data = response_data["Success"]
                    if len(success_data) > 0:
                        # Get the closing price from the daily data
                        daily_data = success_data[0]  # Should be only one day
                        closing_price = float(daily_data.get("close", 0))
                        return {
                            "stock_code": stock_code,
                            "date": target_date,
                            "previous_close": closing_price
                        }
                    else:
                        return {"error": "No data found", "response": f"No data for {target_date}"}
                else:
                    return {"error": "Invalid response structure", "response": response_data}
            
            return {"error": "Empty response", "response": response_data}
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text[:200]}
            
    except Exception as e:
        return {"error": "Exception", "response": str(e)}

# Function to get previous day closing prices for all stocks in CSV
def get_all_previous_day_closes(target_date="2025-10-16", csv_file_path="stock_names_symbol.csv"):
    """
    Get previous day closing prices for all stocks in the CSV file
    
    Args:
        target_date: Date for which to fetch closing prices (YYYY-MM-DD)
        csv_file_path: Path to CSV file with stock codes
    
    Returns:
        Dict with stock_code -> closing_price mapping
    """
    print(f"\n📅 Getting previous day closes for all stocks ({target_date})")
    
    # Load all stock codes from CSV
    print("📊 Loading stocks from CSV...")
    stock_codes = load_stock_codes_from_csv(
        csv_file_path=csv_file_path,
        start_index=0,
        end_index=None  # Get all stocks
    )
    
    if not stock_codes:
        print("❌ Could not load stock codes from CSV")
        return {}
    
    print(f"✅ Loaded {len(stock_codes)} stocks from CSV")
    
    # Get session token
    session_token = get_session_token()
    if not session_token:
        print("❌ Could not get session token")
        return {}
    
    # Fetch previous day closes
    print(f"\n📅 Fetching previous day closes for {len(stock_codes)} stocks...")
    previous_closes = {}
    
    for i, stock_code in enumerate(stock_codes, 1):
        print(f"[{i}/{len(stock_codes)}] {stock_code}: ", end="")
        
        prev_close_data = fetch_previous_day_close(stock_code, session_token, target_date)
        
        if prev_close_data and "error" not in prev_close_data:
            previous_closes[stock_code] = prev_close_data["previous_close"]
            print(f"₹{prev_close_data['previous_close']}")
        else:
            print("❌ Failed")
        
        import time
        time.sleep(0.2)  # Small delay
    
    print(f"\n✅ Successfully retrieved {len(previous_closes)}/{len(stock_codes)} previous day closes")
    print(f"📊 Success rate: {(len(previous_closes)/len(stock_codes)*100):.1f}%")
    
    return previous_closes

# Legacy function (for backward compatibility if someone passes specific stocks)
def get_previous_day_closes(stock_codes, session_token, target_date="2025-10-16"):
    """
    Get previous day closing prices for a list of stocks
    
    Args:
        stock_codes: List of stock symbols
        session_token: API session token
        target_date: Date for which to fetch closing prices (YYYY-MM-DD)
    
    Returns:
        Dict with stock_code -> closing_price mapping
    """
    print(f"\n📅 Fetching previous day closes for {len(stock_codes)} stocks ({target_date})")
    
    previous_closes = {}
    
    for i, stock_code in enumerate(stock_codes, 1):
        print(f"[{i}/{len(stock_codes)}] {stock_code}: ", end="")
        
        prev_close_data = fetch_previous_day_close(stock_code, session_token, target_date)
        
        if prev_close_data and "error" not in prev_close_data:
            previous_closes[stock_code] = prev_close_data["previous_close"]
            print(f"₹{prev_close_data['previous_close']}")
        else:
            print("❌ Failed")
        
        import time
        time.sleep(0.2)  # Small delay
    
    print(f"\n✅ Successfully retrieved {len(previous_closes)} previous day closes")
    return previous_closes

# Main execution (only run when this file is executed directly, not when imported)
if __name__ == "__main__":
    # Load stock codes from CSV
    # You can modify these parameters:
    START_INDEX = 0      # Start from first stock (0-based)
    END_INDEX = None       # End at 10th stock (set to None for all stocks)

    stock_codes = load_stock_codes_from_csv(
        csv_file_path="stock_names_symbol.csv",
        start_index=START_INDEX,
        end_index=END_INDEX
    )

    if not stock_codes:
        print("❌ No stock codes loaded. Exiting...")
        exit(1)
    # Dictionary to store clean OHLC data
    stock_ohlc_data = {}
    failed_stocks = []
    successful_requests = 0
    failed_requests = 0

    print(f"\n🚀 Fetching 5-minute OHLC data for {len(stock_codes)} stocks...")
    print("="*60)

    for i, stock_code in enumerate(stock_codes, 1):
        print(f"[{i}/{len(stock_codes)}] {stock_code}: ", end="")
        
        # Fetch 5-minute interval data for this stock
        data = fetch_historical_data(stock_code, session_token)
        
        if data and "error" not in data:
            # Extract clean OHLC data from API response
            if "Success" in data and data["Success"]:
                candles = []
                for candle in data["Success"]:
                    clean_candle = {
                        "datetime": candle.get("datetime", ""),
                        "open": float(candle.get("open", 0)),
                        "high": float(candle.get("high", 0)),
                        "low": float(candle.get("low", 0)),
                        "close": float(candle.get("close", 0)),
                        "volume": int(candle.get("volume", 0))
                    }
                    candles.append(clean_candle)
                
                stock_ohlc_data[stock_code] = candles
                successful_requests += 1
                print(f"✓ {len(candles)} candles")
            else:
                failed_requests += 1
                failed_stocks.append({
                    "stock_code": stock_code,
                    "error": "No Success data in response"
                })
                print("❌ No data")
        else:
            # Log as failed request
            failed_requests += 1
            failed_stocks.append({
                "stock_code": stock_code,
                "error": data.get("error", "Unknown error") if data else "No response"
            })
            print("❌ Failed")
        
        # Add a small delay to avoid rate limiting
        import time
        time.sleep(0.5)
    
    # Save clean OHLC data
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"Total stocks processed: {len(stock_codes)}")
    print(f"Successful: {successful_requests}")
    print(f"Failed: {failed_requests}")
    print(f"Success rate: {(successful_requests/len(stock_codes)*100):.1f}%")
    
    # Save the clean OHLC data
    if stock_ohlc_data:
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ohlc_filename = f'stock_ohlc_data_{timestamp}.json'
        
        # Create clean structure
        clean_data = {
            "collection_info": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_stocks_requested": len(stock_codes),
                "successful_stocks": successful_requests,
                "failed_stocks": failed_requests,
                "success_rate_percent": round(successful_requests/len(stock_codes)*100, 2),
                "date_range": "2025-10-17T09:10:00.000Z to 2025-10-17T09:30:00.000Z",
                "interval": "5minute",
                "exchange": "NSE"
            },
            "stocks": stock_ohlc_data
        }
    
        try:
            # Ensure directory exists
            os.makedirs('test_folder', exist_ok=True)
            ohlc_path = os.path.join('test_folder', ohlc_filename)
            
            with open(ohlc_path, 'w') as f:
                json.dump(clean_data, f, indent=2)
            
            print(f"\n✅ OHLC data saved to '{ohlc_path}'")
            print(f"   📊 Contains {len(stock_ohlc_data)} stocks")
            
            # Create symlink for easy access
            latest_link = os.path.join('test_folder', 'latest_ohlc_data.json')
            try:
                if os.path.exists(latest_link):
                    os.remove(latest_link)
                os.symlink(ohlc_filename, latest_link)
                print(f"   🔗 Latest data link: '{latest_link}'")
            except Exception as link_error:
                print(f"   ⚠️  Could not create symlink: {link_error}")
                
        except Exception as e:
            print(f"\n❌ Failed to save OHLC data: {e}")
    
    else:
        print("❌ No OHLC data collected")
    
    # Save failed stocks record
    if failed_stocks:
        failed_txt_filename = f'test_folder/failed_stocks_{START_INDEX}_to_{END_INDEX}.txt'
        try:
            os.makedirs('test_folder', exist_ok=True)
            with open(failed_txt_filename, 'w') as f:
                f.write(f"Failed Stock Codes ({len(failed_stocks)} total):\n")
                f.write("=" * 50 + "\n\n")
                for entry in failed_stocks:
                    f.write(f"Stock: {entry['stock_code']}\n")
                    f.write(f"Error: {entry.get('error', 'Unknown')}\n")
                    f.write("-" * 30 + "\n")
            print(f"\n📝 Failed stocks list saved to '{failed_txt_filename}'")
            print(f"   Contains {len(failed_stocks)} failed requests")
            
        except Exception as e:
            print(f"\n❌ Failed to save failed stocks list: {e}")
    
    print("\n" + "="*60)
    print(f"🎯 Data collection completed")
    print("="*60)
    print(f"\n🎉 Process completed!")
    print(f"📁 Clean OHLC data saved")
    print(f"💡 Use get_previous_day_closes() function to get previous day closing prices when needed")

