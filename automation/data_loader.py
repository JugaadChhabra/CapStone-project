"""
ICICI Direct API Data Loader - Clean Version

PURPOSE: Provides essential data loading functions for trading strategy
FOCUS: Previous day closing prices and stock symbol management

FUNCTIONS OVERVIEW:
├── get_session_token() -> Authentication for ICICI Direct API
├── load_stock_codes_from_csv() -> Load stock symbols from CSV  
├── fetch_previous_day_close() -> Get single stock closing price (internal utility)
└── get_all_previous_day_closes() -> Main function: Get all closing prices for strategy

USAGE:
    from data_loader import get_all_previous_day_closes
    previous_closes = get_all_previous_day_closes("2025-10-20")
"""

import requests, json, hashlib, os, helper_functions as hf, pandas as pd
from datetime import datetime, timezone

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

if not all([secret_key, appkey, session_key]):
    raise ValueError("Missing required environment variables: SECRET_KEY, APP_KEY, SESSION_KEY")

def get_session_token():
    """
    USE CASE: Authentication - Get session token from ICICI Direct API
    Required for all API calls to ICICI Direct
    
    Returns:
        str: Session token for API authentication, None if failed
    """
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    payload = json.dumps({
        "SessionToken": session_key,
        "AppKey": appkey
    })
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.get(customerDetail_url, headers=headers, data=payload)
        data = response.json()
        
        if data and "Success" in data and "session_token" in data["Success"]:
            return data["Success"]["session_token"]
        return None
            
    except Exception:
        return None

# Initialize session token
session_token = get_session_token()

def load_stock_codes_from_csv():
    """
    USE CASE: Data Loading - Load all stock symbols from CSV file
    Used by trading strategy to get complete list of stocks to analyze
    
    Returns:
        List[str]: List of stock symbols from CSV second column
    """
    csv_file_path = "data/stock_names_symbol.csv"
    try:
        df = pd.read_csv(csv_file_path, header=None)
        return df[1].tolist()  # Return stock symbols from second column
    except Exception:
        return []

def fetch_previous_day_close(stock_code, session_token, target_date):
    """
    USE CASE: Previous Day Data - Fetch closing price for a single stock
    Internal utility function used by get_all_previous_day_closes()
    
    Args:
        stock_code: Stock symbol
        session_token: API session token  
        target_date: Date for closing price (YYYY-MM-DD format)
    
    Returns:
        Dict: {"stock_code": str, "date": str, "previous_close": float} or {"error": str}
    """
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    
    payload = json.dumps({
        "interval": "day",
        "from_date": f"{target_date}T00:00:00.000Z", 
        "to_date": f"{target_date}T23:59:59.000Z",
        "stock_code": stock_code,
        "exchange_code": "NSE",
        "product_type": "cash"
    }, separators=(',', ':'))
    
    checksum = hashlib.sha256((time_stamp + payload + secret_key).encode("utf-8")).hexdigest()
    
    headers = {
        'Content-Type': 'application/json',
        'X-Checksum': 'token ' + checksum,
        'X-Timestamp': time_stamp,
        'X-AppKey': appkey,
        'X-SessionToken': session_token
    }
    
    try:
        response = requests.get(historical_url, headers=headers, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            if (isinstance(data, dict) and 
                data.get("Error") is None and 
                "Success" in data and 
                data["Success"] and 
                len(data["Success"]) > 0):
                
                closing_price = float(data["Success"][0].get("close", 0))
                return {
                    "stock_code": stock_code,
                    "date": target_date,
                    "previous_close": closing_price
                }
        
        return {"error": "No data available"}
            
    except Exception:
        return {"error": "Request failed"}

def get_all_previous_day_closes(target_date):
    """
    USE CASE: Trading Strategy Core - Get previous day closing prices for all stocks
    Main function used by trading strategy to get baseline prices for percentage calculations
    
    Args:
        target_date: Date for closing prices (YYYY-MM-DD format) - REQUIRED
    
    Returns:
        Dict[str, float]: Mapping of stock_code -> closing_price
    """

    print("🔄 Fetching previous day closing prices for all stocks...")
    
    # Load stock codes and get session token
    stock_codes = load_stock_codes_from_csv()
    session_token = get_session_token()
    
    print(f"📊 Loaded {len(stock_codes)} stock codes from CSV")
    print(f"🔑 Session token: {'Available' if session_token else 'Failed to get'}")
    
    if not stock_codes or not session_token:
        if not stock_codes:
            print("❌ No stock codes loaded from CSV")
        if not session_token:
            print("❌ Failed to get session token")
        return {}
    
    previous_closes = {}
    
    for stock_code in stock_codes:
        prev_close_data = fetch_previous_day_close(stock_code, session_token, target_date)
        
        if prev_close_data and "error" not in prev_close_data:
            previous_closes[stock_code] = prev_close_data["previous_close"]
        
        import time
        time.sleep(0.1)  # Rate limiting
    
    return previous_closes



if __name__ == "__main__":
    """
    USE CASE: Testing - Test the get_all_previous_day_closes function    """

    fetch_for = hf.get_previous_day_close_date()

    result = get_all_previous_day_closes(fetch_for)
    print(f"Retrieved {len(result)} stock prices")