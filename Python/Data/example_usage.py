# Example: How to use the cleaned up stock price function

from Live_Data_Stream import get_stock_prices, get_available_stocks, cleanup

def main():
    # Example 1: Get current prices for specific stocks
    print("🚀 Getting stock prices...")
    
    stocks_to_check = ['Reliance', 'TCS', 'HDFC Bank', 'Infosys', 'ICICI Bank']
    prices = get_stock_prices(stocks_to_check, wait_time=5.0)
    
    print("\n📊 Current Stock Prices:")
    print("=" * 60)
    
    for stock, data in prices.items():
        if data:
            # Calculate percentage change
            current_price = data['price']
            change = data['change']
            percentage_change = (change / (current_price - change)) * 100 if current_price > 0 else 0
            
            trend = "📈" if change >= 0 else "📉"
            print(f"{trend} {stock:<15} | ₹{current_price:>8,.2f} | {change:>+7.2f} ({percentage_change:>+6.2f}%)")
            print(f"   {'':17} | High: ₹{data['high']:,.2f} | Low: ₹{data['low']:,.2f} | Vol: {data['volume']}")
        else:
            print(f"❌ {stock:<15} | No data available")
    
    print("=" * 60)
    
    # Example 2: Check specific conditions (like your trading strategy)
    print("\n🔍 Analyzing for 2% movers:")
    significant_movers = []
    
    for stock, data in prices.items():
        if data:
            current_price = data['price']
            change = data['change']
            percentage_change = (change / (current_price - change)) * 100 if current_price > 0 else 0
            
            if abs(percentage_change) >= 2.0:  # 2% or more movement
                significant_movers.append({
                    'stock': stock,
                    'price': current_price,
                    'change_percent': percentage_change,
                    'direction': 'UP' if percentage_change > 0 else 'DOWN'
                })
    
    if significant_movers:
        print("Found stocks with 2%+ movement:")
        for mover in significant_movers:
            direction_symbol = "🚀" if mover['direction'] == 'UP' else "🔻"
            print(f"  {direction_symbol} {mover['stock']}: {mover['change_percent']:+.2f}% (₹{mover['price']:,.2f})")
    else:
        print("No stocks found with 2%+ movement at this time.")
    
    # Example 3: Show available stocks
    print(f"\n📋 Available stocks (first 15):")
    available = get_available_stocks()
    for i, stock in enumerate(available[:15]):
        print(f"   {i+1:2d}. {stock}")
    
    if len(available) > 15:
        print(f"   ... and {len(available) - 15} more stocks available")
    
    # Always cleanup when done
    cleanup()
    print("\n✅ Done!")

if __name__ == "__main__":
    main()