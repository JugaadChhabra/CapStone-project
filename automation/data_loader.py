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

import requests, json, helper_functions as hf
from typing import Dict
from icici_functions import (
    get_session_token, 
    load_stock_data_from_csv, 
    create_api_headers,
    HISTORICAL_URL
)

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
    
    for stock_code in stock_codes:
        prev_close_data = fetch_previous_day_close(stock_code, session_token, target_date)
        
        if prev_close_data and "error" not in prev_close_data:
            previous_closes[stock_code] = prev_close_data["previous_close"]
        
        import time
        time.sleep(0.1)  # Rate limiting
    
    print(f"📊 Successfully retrieved {len(previous_closes)} closing prices")
    return previous_closes



if __name__ == "__main__":
    """
    USE CASE: Testing - Test the get_all_previous_day_closes function    """

    fetch_for = hf.get_previous_day_close_date()

    result = get_all_previous_day_closes(fetch_for)
    print(f"Retrieved {len(result)} stock prices")