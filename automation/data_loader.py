"""
ICICI Direct API Data Loader - Refactored Version

PURPOSE: Provides essential data loading functions for trading strategy
FOCUS: Previous day closing prices using centralized ICICI API utilities

FUNCTIONS OVERVIEW:
├── fetch_previous_day_close() -> Get single stock closing price (internal utility)
└── get_all_previous_day_closes() -> Main function: Get all closing prices for strategy

USAGE:
    from data_loader import get_all_previous_day_closes
    previous_closes = get_all_previous_day_closes("2025-10-20")
"""

import requests, json
from typing import Dict
from datetime import datetime, timedelta
from icici_functions import (
    get_session_token, 
    load_stock_data_from_csv, 
    create_api_headers,
    HISTORICAL_URL
)

def get_previous_day_close_date():
    """Calculate the previous trading day date"""
    today = datetime.now()
    
    # If today is Monday (0), go back 3 days to Friday
    if today.weekday() == 0:  # Monday
        target_date = today - timedelta(days=3)
    else:
        target_date = today - timedelta(days=1)
        
    return target_date.strftime("%Y-%m-%d")

def fetch_previous_day_close(stock_code: str, session_token: str, target_date: str) -> Dict:
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
    payload = json.dumps({
        "interval": "day",
        "from_date": f"{target_date}T00:00:00.000Z", 
        "to_date": f"{target_date}T23:59:59.000Z",
        "stock_code": stock_code,
        "exchange_code": "NSE",
        "product_type": "cash"
    }, separators=(',', ':'))
    
    headers = create_api_headers(payload, session_token)
    
    try:
        response = requests.get(HISTORICAL_URL, headers=headers, data=payload)
        
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

def get_all_previous_day_closes(target_date: str) -> Dict[str, float]:
    """
    USE CASE: Trading Strategy Core - Get previous day closing prices for all stocks
    Main function used by trading strategy to get baseline prices for percentage calculations
    
    Args:
        target_date: Date for closing prices (YYYY-MM-DD format) - REQUIRED
    
    Returns:
        Dict[str, float]: Mapping of stock_code -> closing_price
    """
    print("🔄 Fetching previous day closing prices for all stocks...")
    
    # Check market timing
    current_time = datetime.now().time()
    market_open = datetime.now().replace(hour=9, minute=15).time()
    market_close = datetime.now().replace(hour=15, minute=30).time()
    is_market_hours = market_open <= current_time <= market_close
    
    if not is_market_hours:
        print(f"⚠️  Market is currently CLOSED (Current: {current_time.strftime('%H:%M:%S')})")
        print("   Market hours: 09:15 AM - 03:30 PM IST")
        print("   Historical data APIs may not work outside market hours")
    
    # Load stock codes and get session token using centralized utilities
    stock_codes = load_stock_data_from_csv('symbols_only')
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
    failed_count = 0
    
    # Test with first stock to see if API is working
    if stock_codes:
        print(f"🧪 Testing API with first stock: {stock_codes[0]}")
        test_result = fetch_previous_day_close(stock_codes[0], session_token, target_date)
        
        if "error" in test_result:
            print(f"❌ API test failed: {test_result['error']}")
            print("   Possible reasons:")
            print("   - Market closed (historical APIs may be limited)")
            print("   - Invalid date (market holiday)")
            print("   - API rate limiting")
            print("   - Session token expired")
            return {}
        else:
            print(f"✅ API test successful: {test_result}")
    
    # Limit to first 10 stocks for faster testing during development
    max_stocks = 10 if not is_market_hours else len(stock_codes)
    print(f"📊 Fetching data for {max_stocks} stocks (limited for testing)")
    
    for i, stock_code in enumerate(stock_codes[:max_stocks]):
        if i > 0 and i % 5 == 0:
            print(f"   Progress: {i}/{max_stocks} stocks processed...")
            
        prev_close_data = fetch_previous_day_close(stock_code, session_token, target_date)
        
        if prev_close_data and "error" not in prev_close_data:
            previous_closes[stock_code] = prev_close_data["previous_close"]
        else:
            failed_count += 1
            
        import time
        time.sleep(0.2)  # Slightly longer rate limiting
    
    print(f"📊 Successfully retrieved {len(previous_closes)} closing prices")
    print(f"❌ Failed to get {failed_count} closing prices")
    
    if len(previous_closes) == 0:
        print("⚠️  No closing prices retrieved - this is expected outside market hours")
    
    return previous_closes



if __name__ == "__main__":
    """
    USE CASE: Testing - Test the get_all_previous_day_closes function    """

    fetch_for = get_previous_day_close_date()

    result = get_all_previous_day_closes(fetch_for)
    print(f"Retrieved {len(result)} stock prices")