import os, requests, json, hashlib, base64, pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional, Literal

CUSTOMER_DETAIL_URL = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
HISTORICAL_URL = "https://api.icicidirect.com/breezeapi/api/v1/historicalcharts"
WEBSOCKET_URL = "https://livestream.icicidirect.com"
CSV_FILE_PATH = "data/stock_names_symbol.csv"

def get_env_config() -> Dict[str, str]:
    """
    USE CASE: Configuration - Load and return environment variables
    Simple function to get all required ICICI API credentials
    
    Returns:
        Dict containing secret_key, app_key, session_key
    
    Raises:
        ValueError: If any required environment variable is missing
    """
    load_dotenv()
    secret_key = os.getenv("SECRET_KEY")
    app_key = os.getenv("APP_KEY") 
    session_key = os.getenv("API_SESSION_TOKEN")

    if not all([secret_key, app_key, session_key]):
        raise ValueError("Missing required environment variables: SECRET_KEY, APP_KEY, SESSION_KEY")
    
    return {
        'secret_key': secret_key,
        'app_key': app_key,
        'session_key': session_key
    }

def get_session_token() -> Optional[str]:
    """
    USE CASE: Authentication - Get session token from ICICI Direct API
    Unified implementation eliminating duplication between data_loader.py and live_data_stream.py
    
    Returns:
        str: Session token for API authentication, None if failed
    """
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'

    config = get_env_config()

    payload = json.dumps({
        "SessionToken": config['session_key'],
        "AppKey": config['app_key']
    })
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.get(CUSTOMER_DETAIL_URL, headers=headers, data=payload)
        data = response.json()
        
        if data and "Success" in data and "session_token" in data["Success"]:
            return data["Success"]["session_token"]
        return None
            
    except Exception:
        return None
    
def get_websocket_session() -> Tuple[Optional[str], Optional[str]]:
    """
    USE CASE: WebSocket Authentication - Get WebSocket session credentials
    Extracts user_id and session_token for WebSocket connections
    
    Returns:
        Tuple[user_id, websocket_session_token]: Both strings or (None, None) if failed
    """

    config = get_env_config()

    try:
        payload = json.dumps({
            "SessionToken": config['session_key'],
            "AppKey": config['app_key']
        })
        headers = {'Content-Type': 'application/json'}
        
        response = requests.get(CUSTOMER_DETAIL_URL, headers=headers, data=payload)
        data = response.json()
        
        if data.get("Success") and "session_token" in data["Success"]:
            websocket_session_key = data["Success"]["session_token"]
            decoded = base64.b64decode(websocket_session_key.encode('ascii')).decode('ascii')
            user_id, session_token = decoded.split(":")
            return user_id, session_token
        else:
            return None, None
            
    except Exception:
        return None, None

def create_api_headers(payload: str, session_token: str) -> Dict[str, str]:
    """
    USE CASE: API Request Headers - Generate standardized API headers
    Centralizes header creation logic for all ICICI API calls
    
    Args:
        payload: JSON payload as string
        session_token: Session token for authentication
    
    Returns:
        Dict containing all required headers for ICICI API calls
    """
    time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
    config = get_env_config()
    
    checksum = hashlib.sha256((time_stamp + payload + config['secret_key']).encode("utf-8")).hexdigest()

    
    return {
        'Content-Type': 'application/json',
        'X-Checksum': 'token ' + checksum,
        'X-Timestamp': time_stamp,
        'X-AppKey': config['app_key'],
        'X-SessionToken': session_token
    }

def load_stock_data_from_csv(
    format: Literal['symbols_only', 'full_data', 'websocket_ready'] = 'symbols_only'
) -> List:
    """
    USE CASE: Data Loading - Unified CSV loading with multiple return formats
    Replaces duplicate CSV loading functions in data_loader.py and live_data_stream.py
    
    Args:
        format: Return format
            - 'symbols_only': List[str] - Just stock symbols (for data_loader.py)
            - 'full_data': List[Dict] - Complete stock data (for analysis)
            - 'websocket_ready': Tuple[List[Dict], List[str]] - Stock data + websocket codes (for live_data_stream.py)
    
    Returns:
        Format-dependent return as specified above
    """
    try:
        # Handle both absolute and relative paths
        if os.path.exists(CSV_FILE_PATH):
            csv_path = CSV_FILE_PATH
        else:
            # Try relative path from current directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(script_dir, CSV_FILE_PATH)
        
        df = pd.read_csv(csv_path, header=None, names=['company_name', 'symbol', 'token'])
        
        if format == 'symbols_only':
            return df['symbol'].tolist()
        
        elif format == 'full_data':
            stock_data = []
            for _, row in df.iterrows():
                company_name = str(row['company_name']).strip()
                symbol = str(row['symbol']).strip()
                token = str(row['token']).strip()
                
                if company_name and symbol and token and token != 'nan':
                    stock_data.append({
                        'company_name': company_name,
                        'symbol': symbol,
                        'token': token
                    })
            return stock_data
        
        elif format == 'websocket_ready':
            stock_data = []
            websocket_codes = []
            
            for _, row in df.iterrows():
                company_name = str(row['company_name']).strip()
                symbol = str(row['symbol']).strip()
                token = str(row['token']).strip()
                
                if not company_name or not symbol or not token or token == 'nan':
                    continue
                
                # Create WebSocket code
                if symbol.upper() in ['NIFTY', 'SENSEX', 'BANKNIFTY']:
                    websocket_code = symbol.upper()
                else:
                    websocket_code = f"4.1!{token}"
                
                stock_data.append({
                    'symbol': symbol,
                    'token': token,
                    'websocket_code': websocket_code
                })
                websocket_codes.append(websocket_code)
            
            return stock_data, websocket_codes
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        if format == 'websocket_ready':
            return [], []
        return []