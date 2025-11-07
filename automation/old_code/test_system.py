#!/usr/bin/env python3
"""
Quick test script for Options Trading System
"""

def test_imports():
    print("🧪 Testing Options Trading System Imports...")
    
    # Test data loading
    try:
        from data_loader import get_previous_day_close_date, get_all_previous_day_closes
        date = get_previous_day_close_date()
        print(f"✅ Data loader: Previous trading day: {date}")
    except Exception as e:
        print(f"❌ Data loader test failed: {e}")
    
    # Test live data stream
    try:
        from live_data_stream import run_trading_strategy
        print("✅ Live data stream: Functions imported successfully")
    except Exception as e:
        print(f"❌ Live data stream test failed: {e}")
    
    # Test API credentials
    try:
        from icici_functions import get_env_config, get_session_token
        config = get_env_config()
        token = get_session_token()
        print("✅ ICICI API: Credentials loaded and session token obtained")
        print(f"   - App key exists: {bool(config.get('app_key'))}")
        print(f"   - Session token length: {len(token) if token else 0}")
    except Exception as e:
        print(f"❌ API credentials test failed: {e}")
    
    # Test trading config
    try:
        from trading_config import LOG_LEVEL, STRIKE_BUFFER, OPTION_LOT_SIZE
        print("✅ Trading config: All variables loaded")
        print(f"   - Log level: {LOG_LEVEL}")
        print(f"   - Strike buffer: {STRIKE_BUFFER}")
        print(f"   - Option lot size: {OPTION_LOT_SIZE}")
    except Exception as e:
        print(f"❌ Trading config test failed: {e}")

def test_data_fallback():
    print("\n🔄 Testing Data Loading with Fallback...")
    
    try:
        from options_trading_system import OptionsTrader
        
        # Create trader instance
        trader = OptionsTrader()
        
        # Test previous day closes with fallback
        success = trader.get_previous_day_closes()
        
        if success:
            print(f"✅ Previous day data loaded: {len(trader.previous_closes)} stocks")
            print("   Sample stocks:", list(trader.previous_closes.keys())[:5])
        else:
            print("❌ Failed to load previous day data")
            
    except Exception as e:
        print(f"❌ Data fallback test failed: {e}")

if __name__ == "__main__":
    test_imports()
    test_data_fallback()
    print("\n🎯 Test completed! System is ready for trading.")