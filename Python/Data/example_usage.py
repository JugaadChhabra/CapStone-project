from Live_Data_Stream import get_stock_prices, cleanup

# Simple usage - get stock prices
stocks = ['Reliance', 'TCS', 'HDFC Bank']
prices = get_stock_prices(stocks)

# Print results
for stock, data in prices.items():
    if data:
        print(f"{stock}: ₹{data['price']:.2f} (Change: {data['change']:+.2f})")

# Cleanup
cleanup()