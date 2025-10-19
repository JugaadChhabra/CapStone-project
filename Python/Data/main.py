import Live_Data_Stream
import DataLoader
import json
import os
from datetime import datetime

# Main execution
print("🚀 Testing get_all_previous_day_closes function...")

previous_closes = DataLoader.get_all_previous_day_closes(target_date="2025-10-16")

print(f"\n📊 Final Results:")
if previous_closes:
    sample_stocks = list(previous_closes.items())[:10]
    print("Sample results (first 10 stocks):")
    for stock, price in sample_stocks:
        print(f"{stock}: ₹{price}")
    
    if len(previous_closes) > 10:
        print(f"     ... and {len(previous_closes) - 10} more stocks")
        
    results_file = f"previous_day_closes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    results_data = {
        "collection_info": {
            "timestamp": datetime.now().isoformat(),
            "successful_stocks": len(previous_closes),
            "target_date": "2025-10-16",
            "source": "All stocks from stock_names_symbol.csv"
        },
        "previous_closes": previous_closes
    }
    
    try:
        os.makedirs('test_folder', exist_ok=True)
        with open(f'test_folder/{results_file}', 'w') as f:
            json.dump(results_data, f, indent=2)
        print(f"💾 Results saved to: test_folder/{results_file}")
    except Exception as e:
        print(f"⚠️  Could not save results: {e}")
        
else:
    print("No previous day closes retrieved")

