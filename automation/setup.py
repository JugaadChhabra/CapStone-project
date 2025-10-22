#!/usr/bin/env python3
"""
Automated Trading Bot Setup Script

This script helps you set up the automated trading bot for the first time.
It will check dependencies and guide you through the setup process.
"""

import os
import sys
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def check_dependencies():
    """Check if required Python packages are installed"""
    required_packages = [
        ('requests', 'requests'),
        ('pandas', 'pandas'), 
        ('python-dotenv', 'dotenv'),
        ('python-socketio', 'socketio'),
        ('selenium', 'selenium')  # Required for OI scraping
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✅ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            print(f"❌ {package_name}")
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_files():
    """Check if all required files exist"""
    required_files = [
        'icici_functions.py',
        'websocket_connection.py',
        'live_data_stream.py',  # Changed to lowercase
        'data_loader.py',
        'auto_trader.py',
        'run_trader.py',
        'trading_config.py',
        'scraping.py',  # Essential for live OI data
        'order_management.py'  # Real order placement API
    ]
    
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            missing_files.append(file)
            print(f"❌ {file}")
    
    if missing_files:
        print(f"\n❌ Missing required files: {missing_files}")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists with required variables"""
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("\n📝 Creating sample .env file...")
        
        sample_env = """# ICICI Direct API Credentials
# Get these from your ICICI Direct developer account

SECRET_KEY=your_secret_key_here
APP_KEY=your_app_key_here  
API_SESSION_TOKEN=your_session_token_here

# Optional: Notification settings (for future use)
# PHONE_NUMBER=+91xxxxxxxxxx
# EMAIL_ADDRESS=your@email.com
# TELEGRAM_BOT_TOKEN=your_telegram_bot_token
# TELEGRAM_CHAT_ID=your_chat_id
"""
        
        with open('.env', 'w') as f:
            f.write(sample_env)
        
        print("✅ Sample .env file created")
        print("🔧 Please edit .env file and add your ICICI Direct API credentials")
        return False
    
    # Check if .env has the required variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['SECRET_KEY', 'APP_KEY', 'API_SESSION_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var) or os.getenv(var) == f'your_{var.lower()}_here':
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing/placeholder values in .env: {missing_vars}")
        print("🔧 Please update your .env file with actual API credentials")
        return False
    
    print("✅ .env file configured properly")
    return True

def check_data_directory():
    """Check if data directory and CSV file exist"""
    data_dir = Path('data')
    csv_file = data_dir / 'stock_names_symbol.csv'
    
    if not data_dir.exists():
        print("❌ data/ directory not found")
        print("📁 Creating data/ directory...")
        data_dir.mkdir()
        print("✅ data/ directory created")
    else:
        print("✅ data/ directory exists")
    
    if not csv_file.exists():
        print("❌ stock_names_symbol.csv not found in data/ directory")
        print("📋 This file should contain stock symbols and codes for trading")
        print("🔧 Please add your stock data CSV file to data/stock_names_symbol.csv")
        return False
    else:
        print("✅ stock_names_symbol.csv found")
        return True

def main():
    """Main setup function"""
    print("🔧 AUTOMATED TRADING BOT SETUP")
    print("=" * 50)
    
    checks_passed = 0
    total_checks = 5
    
    print("\n1️⃣ Checking Python version...")
    if check_python_version():
        checks_passed += 1
    
    print("\n2️⃣ Checking dependencies...")
    if check_dependencies():
        checks_passed += 1
    
    print("\n3️⃣ Checking required files...")
    if check_files():
        checks_passed += 1
    
    print("\n4️⃣ Checking environment configuration...")
    if check_env_file():
        checks_passed += 1
    
    print("\n5️⃣ Checking data files...")
    if check_data_directory():
        checks_passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Setup Status: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed == total_checks:
        print("🎉 SETUP COMPLETE!")
        print("✅ All requirements met")
        print("\n🚀 You can now run the trading bot:")
        print("   python3 run_trader.py")
        print("\n⚙️  To customize settings:")
        print("   Edit trading_config.py")
        return True
    else:
        print("⚠️  SETUP INCOMPLETE")
        print(f"❌ {total_checks - checks_passed} issues need to be resolved")
        print("\n🔧 Please fix the issues above and run setup again")
        return False

if __name__ == "__main__":
    main()