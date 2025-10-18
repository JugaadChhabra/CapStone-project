import json
import os
from datetime import datetime, time
from typing import List, Dict, Any
import pandas as pd

class TradingStrategyBacktest:
    def __init__(self, json_data_file: str):
        """
        Initialize backtest with JSON data file
        
        Args:
            json_data_file: Path to JSON file containing historical data
        """
        self.json_data_file = json_data_file
        self.stock_data = []
        self.backtest_data = {}
        self.movers_920 = []
        self.final_stocks_925 = []
        
        # Load CSV stock data for symbol mapping
        self.load_stock_data()
        
        # Load JSON backtest data
        self.load_backtest_data()
    
    def load_stock_data(self, csv_file_path="stock_names_symbol.csv"):
        """Load stock data from CSV file"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(script_dir, csv_file_path)
            
            df = pd.read_csv(csv_path, header=None, names=['company_name', 'symbol', 'token'])
            
            for _, row in df.iterrows():
                symbol = str(row['symbol']).strip()
                token = str(row['token']).strip()
                
                if not symbol or not token or token == 'nan':
                    continue
                
                websocket_code = f"4.1!{token}" if symbol.upper() not in ['NIFTY', 'SENSEX', 'BANKNIFTY'] else symbol.upper()
                
                self.stock_data.append({
                    'symbol': symbol,
                    'token': token,
                    'websocket_code': websocket_code
                })
            
            print(f"📊 Loaded {len(self.stock_data)} stocks from CSV")
            
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            self.stock_data = []
    
    def load_backtest_data(self):
        """Load historical data from JSON file"""
        try:
            with open(self.json_data_file, 'r') as f:
                self.backtest_data = json.load(f)
            
            print(f"📈 Loaded backtest data from {self.json_data_file}")
            
            # Show available dates/times
            if 'timestamps' in self.backtest_data:
                print(f"   Available timestamps: {list(self.backtest_data['timestamps'].keys())}")
            
        except Exception as e:
            print(f"❌ Error loading JSON data: {e}")
            self.backtest_data = {}
    
    def calculate_percentage_change(self, current_price: float, change: float) -> float:
        """Calculate percentage change"""
        if current_price > 0 and change != 0:
            return (change / (current_price - change)) * 100
        return 0
    
    def get_price_data_at_time(self, timestamp: str) -> Dict[str, Dict]:
        """
        Get price data for all stocks at a specific timestamp
        
        Args:
            timestamp: Time in format "09:20" or "09:25"
            
        Returns:
            Dict with websocket_code as key and price data as value
        """
        if 'timestamps' not in self.backtest_data:
            print(f"❌ No timestamps found in backtest data")
            return {}
        
        if timestamp not in self.backtest_data['timestamps']:
            print(f"❌ Timestamp {timestamp} not found in backtest data")
            available = list(self.backtest_data['timestamps'].keys())
            print(f"   Available: {available}")
            return {}
        
        timestamp_data = self.backtest_data['timestamps'][timestamp]
        
        # Convert to the format expected by the strategy
        price_data = {}
        for stock_symbol, data in timestamp_data.items():
            # Find websocket code for this symbol
            websocket_code = None
            for stock in self.stock_data:
                if stock['symbol'] == stock_symbol:
                    websocket_code = stock['websocket_code']
                    break
            
            if websocket_code:
                price_data[websocket_code] = {
                    'symbol': websocket_code,
                    'price': float(data.get('price', 0)),
                    'change': float(data.get('change', 0)),
                    'high': float(data.get('high', 0)),
                    'low': float(data.get('low', 0)),
                    'open': float(data.get('open', 0)),
                    'volume': data.get('volume', 0),
                    'timestamp': datetime.now()
                }
        
        return price_data
    
    def find_2_percent_movers_backtest(self, timestamp: str = "09:20") -> List[str]:
        """Find stocks with 2%+ movement at specified time"""
        print(f"🎯 Backtest: Finding 2% movers at {timestamp}")
        
        price_data = self.get_price_data_at_time(timestamp)
        
        if not price_data:
            return []
        
        movers = []
        for websocket_code, data in price_data.items():
            # Find corresponding stock symbol
            for stock in self.stock_data:
                if stock['websocket_code'] == websocket_code:
                    percentage_change = self.calculate_percentage_change(data['price'], data['change'])
                    
                    if abs(percentage_change) >= 2.0:
                        movers.append({
                            'symbol': stock['symbol'],
                            'token': stock['token'],
                            'websocket_code': websocket_code,
                            'price_920': data['price'],
                            'change_920': data['change'],
                            'percentage_920': percentage_change
                        })
                    break
        
        self.movers_920 = movers
        symbols = [mover['symbol'] for mover in movers]
        
        print(f"🔍 Found {len(movers)} stocks with 2%+ movement:")
        for mover in movers:
            direction = "📈" if mover['change_920'] >= 0 else "📉"
            print(f"   {direction} {mover['symbol']}: {mover['percentage_920']:+.2f}%")
        
        return symbols
    
    def check_momentum_maintained_backtest(self, timestamp: str = "09:25") -> List[str]:
        """Check which stocks maintained momentum from 9:20 to specified time"""
        print(f"🎯 Backtest: Checking momentum at {timestamp}")
        
        if not self.movers_920:
            print("⚠️  No 9:20 movers data found. Run find_2_percent_movers_backtest first.")
            return []
        
        price_data = self.get_price_data_at_time(timestamp)
        
        if not price_data:
            return []
        
        maintained = []
        for mover in self.movers_920:
            websocket_code = mover['websocket_code']
            
            if websocket_code in price_data:
                current_data = price_data[websocket_code]
                current_percentage = self.calculate_percentage_change(current_data['price'], current_data['change'])
                original_percentage = mover['percentage_920']
                
                # Check if momentum is maintained (not retraced more than 50%)
                if original_percentage > 0:  # Was positive at 9:20
                    if current_percentage >= (original_percentage * 0.5):
                        maintained.append(mover['symbol'])
                else:  # Was negative at 9:20
                    if current_percentage <= (original_percentage * 0.5):
                        maintained.append(mover['symbol'])
        
        self.final_stocks_925 = maintained
        
        print(f"⚡ {len(maintained)} stocks maintained momentum:")
        for symbol in maintained:
            print(f"   📊 {symbol}")
        
        return maintained
    
    def run_backtest_strategy(self, timestamp_920: str = "09:20", timestamp_925: str = "09:25") -> Dict[str, Any]:
        """
        Run the complete backtest strategy
        
        Args:
            timestamp_920: Timestamp for finding 2% movers
            timestamp_925: Timestamp for checking momentum
        
        Returns:
            Dict containing backtest results
        """
        print("🚀 Starting Backtest Strategy")
        print("=" * 60)
        
        # Step 1: Find 2% movers at 9:20
        movers_920 = self.find_2_percent_movers_backtest(timestamp_920)
        
        print("\n" + "=" * 60)
        
        # Step 2: Check momentum at 9:25
        final_stocks = self.check_momentum_maintained_backtest(timestamp_925)
        
        # Calculate success metrics
        total_stocks = len(self.stock_data)
        movers_count = len(movers_920)
        final_count = len(final_stocks)
        
        success_rate = (final_count / movers_count * 100) if movers_count > 0 else 0
        
        results = {
            'timestamp_920': timestamp_920,
            'timestamp_925': timestamp_925,
            'total_stocks_analyzed': total_stocks,
            'movers_920_count': movers_count,
            'movers_920_symbols': movers_920,
            'final_stocks_count': final_count,
            'final_stocks_symbols': final_stocks,
            'momentum_success_rate': success_rate,
            'detailed_movers_920': self.movers_920,
            'strategy_effective': final_count > 0
        }
        
        print("\n📊 Backtest Results:")
        print("=" * 60)
        print(f"Total Stocks Analyzed: {total_stocks}")
        print(f"2% Movers at {timestamp_920}: {movers_count}")
        print(f"Momentum Maintained at {timestamp_925}: {final_count}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Strategy Effective: {'✅ Yes' if results['strategy_effective'] else '❌ No'}")
        
        if final_stocks:
            print(f"\n🎯 Final Trading Symbols:")
            for i, symbol in enumerate(final_stocks, 1):
                print(f"   {i:2d}. {symbol}")
        
        return results
    
    def validate_strategy_data(self) -> bool:
        """
        Validate that the JSON data is suitable for the 9:20/9:25 trading strategy
        
        Returns:
            True if data is valid, False otherwise
        """
        print("🔍 Validating Strategy Data")
        print("=" * 60)
        
        # Check if we have the required timestamps
        if 'timestamps' not in self.backtest_data:
            print("❌ No 'timestamps' section found in JSON data")
            return False
        
        timestamps = self.backtest_data['timestamps']
        required_times = ['09:20', '09:25']
        
        for req_time in required_times:
            if req_time not in timestamps:
                print(f"❌ Missing required timestamp: {req_time}")
                print(f"   Available timestamps: {list(timestamps.keys())}")
                return False
        
        print("✅ Found required timestamps: 09:20 and 09:25")
        
        # Check stocks data at both timestamps
        stocks_920 = set(timestamps['09:20'].keys())
        stocks_925 = set(timestamps['09:25'].keys())
        common_stocks = stocks_920.intersection(stocks_925)
        
        print(f"📊 Stocks at 09:20: {len(stocks_920)}")
        print(f"📊 Stocks at 09:25: {len(stocks_925)}")
        print(f"📊 Common stocks (both timestamps): {len(common_stocks)}")
        
        if len(common_stocks) == 0:
            print("❌ No stocks have data at both required timestamps")
            return False
        
        # Validate data structure for a few sample stocks
        sample_stock = list(common_stocks)[0]
        required_fields = ['price', 'change']
        
        for timestamp in required_times:
            stock_data = timestamps[timestamp][sample_stock]
            for field in required_fields:
                if field not in stock_data:
                    print(f"❌ Missing required field '{field}' for {sample_stock} at {timestamp}")
                    return False
        
        print("✅ Data structure validation passed")
        print(f"✅ Strategy data is valid for {len(common_stocks)} stocks")
        
        return True
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """
        Get a summary of what the strategy will test
        
        Returns:
            Summary information about the strategy setup
        """
        if not self.validate_strategy_data():
            return {'valid': False, 'error': 'Invalid data structure'}
        
        timestamps = self.backtest_data['timestamps']
        stocks_920 = set(timestamps['09:20'].keys())
        stocks_925 = set(timestamps['09:25'].keys())
        common_stocks = stocks_920.intersection(stocks_925)
        
        return {
            'valid': True,
            'strategy_name': 'First Two Candles Momentum Strategy',
            'description': 'Find 2%+ movers at 9:20 AM (first 5-min candle) and check momentum maintenance at 9:25 AM (second 5-min candle)',
            'timestamp_920': '09:20',
            'timestamp_925': '09:25',
            'total_stocks_available': len(common_stocks),
            'data_source': self.json_data_file,
            'strategy_logic': [
                '1. At 9:20 AM: Identify stocks with ±2% price movement',
                '2. At 9:25 AM: Check if momentum is maintained (>50% of original move)',
                '3. Final selection: Stocks that maintain momentum for trading'
            ]
        }

def main():
    """Example usage of the backtest system for 9:20/9:25 strategy"""
    
    # Initialize backtest (you'll provide the JSON file)
    json_file = "backtest_data.json"  # You'll create this with 09:20 and 09:25 data
    
    try:
        backtest = TradingStrategyBacktest(json_file)
        
        # Validate that data is suitable for this specific strategy
        if not backtest.validate_strategy_data():
            print("❌ JSON data is not suitable for the 9:20/9:25 trading strategy")
            print("\nRequired JSON format:")
            print("""
{
    "timestamps": {
        "09:20": {
            "STOCK_SYMBOL": {
                "price": 100.0,
                "change": 2.5,
                "high": 102.0,
                "low": 99.5,
                "open": 100.0,
                "volume": 1000
            }
        },
        "09:25": {
            "STOCK_SYMBOL": {
                "price": 101.0,
                "change": 3.0,
                "high": 103.0,
                "low": 99.5,
                "open": 100.0,
                "volume": 1500
            }
        }
    }
}
            """)
            return
        
        # Show strategy summary
        summary = backtest.get_strategy_summary()
        print(f"\n📋 Strategy: {summary['strategy_name']}")
        print(f"📄 Description: {summary['description']}")
        print(f"📊 Stocks Available: {summary['total_stocks_available']}")
        
        # Run the strategy for the specific 9:20/9:25 timestamps
        print("\n" + "🚀" * 20)
        results = backtest.run_backtest_strategy("09:20", "09:25")
        
        # Save results to file
        output_file = "strategy_backtest_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"❌ JSON file '{json_file}' not found.")
        print("📋 Please create the JSON file with historical data for 09:20 and 09:25 timestamps")
    except Exception as e:
        print(f"❌ Error running backtest: {e}")

if __name__ == "__main__":
    main()