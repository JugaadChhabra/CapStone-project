#!/usr/bin/env python3
"""
Simple Automated Trading Bot Runner

USAGE: Just run this file and let it handle everything automatically!

    python3 run_trader.py

FEATURES:
✅ Waits for market open (9:15 AM)
✅ Executes strategy at 9:20 AM  
✅ Places trades automatically
✅ Monitors positions with stop loss/targets
✅ Closes all positions at market close (3:30 PM)
✅ Generates daily trading summary
✅ Handles graceful shutdown (Ctrl+C)

The bot will:
1. Find 2% movers using our optimized strategy
2. Place trades with automatic risk management
3. Monitor positions throughout the day
4. Close everything at market close
5. Save a complete trading summary

Just run it and walk away! 🚀
"""

import os
import sys
from datetime import datetime

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    # Check if we're in the right directory
    required_files = [
        'icici_functions.py',
        'websocket_connection.py', 
        'Live_Data_Stream.py',
        'data_loader.py',
        'auto_trader.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        print("Please make sure you're running this from the Automation directory")
        return False
    
    # Check environment file
    if not os.path.exists('.env'):
        print("❌ Missing .env file with API credentials")
        print("Please create .env file with SECRET_KEY, APP_KEY, and API_SESSION_TOKEN")
        return False
    
    print("✅ All requirements met!")
    return True

def main():
    """Simple main function to start the trader"""
    print("🤖 AUTOMATED TRADING BOT")
    print("=" * 50)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    print("🚀 Starting automated trader...")
    print("💡 Press Ctrl+C anytime to stop and close all positions")
    print("📊 Trading log will be saved automatically")
    print("💰 Daily summary will be generated at the end")
    print("-" * 50)
    
    try:
        # Import and run the automated trader
        from auto_trader import AutomatedTrader
        
        trader = AutomatedTrader()
        trader.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Manual stop requested. Shutting down safely...")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()