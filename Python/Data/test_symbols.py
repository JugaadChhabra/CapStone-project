import pandas as pd
import csv

def update_stock_symbols():
    """
    Update stock symbols in stock_names_symbol.csv by matching company names 
    with the actual symbols from StockScriptNew.csv and fill missing token values
    """
    
    print("🔍 Starting symbol matching and missing token extraction process...")
    
    # Read stock_names_symbol.csv (assuming it now has 3 columns: name, symbol, token)
    print("📖 Reading stock_names_symbol.csv...")
    try:
        stock_names_df = pd.read_csv('stock_names_symbol.csv', header=None, names=['company_name', 'current_symbol', 'token'])
        print(f"   Found {len(stock_names_df)} stocks in stock_names_symbol.csv")
    except:
        # Fallback if file only has 2 columns
        stock_names_df = pd.read_csv('stock_names_symbol.csv', header=None, names=['company_name', 'current_symbol'])
        stock_names_df['token'] = ''
        print(f"   Found {len(stock_names_df)} stocks in stock_names_symbol.csv (added token column)")
    
    # Fill NaN values with empty strings
    stock_names_df = stock_names_df.fillna('')
    
    # Count missing tokens
    missing_tokens = stock_names_df[stock_names_df['token'] == '']
    print(f"   Found {len(missing_tokens)} stocks with missing tokens")
    
    # Read StockScriptNew.csv (with headers)
    print("📖 Reading StockScriptNew.csv...")
    stock_script_df = pd.read_csv('StockScriptNew.csv')
    print(f"   Found {len(stock_script_df)} entries in StockScriptNew.csv")
    
    # Filter for NSE equity stocks only (most common for trading)
    nse_stocks = stock_script_df[
        (stock_script_df['EC'] == 'NSE') & 
        (stock_script_df['SG'] == 'EQUITY')
    ].copy()
    print(f"   Filtered to {len(nse_stocks)} NSE equity stocks")
    
    # Track updates
    updated_symbols = []
    tokens_filled = []
    not_found_stocks = []
    
    print("\n🔄 Processing missing tokens and symbol validation...")
    print("=" * 80)
    
    for index, row in stock_names_df.iterrows():
        company_name = row['company_name'].strip()
        current_symbol = row['current_symbol'].strip()
        current_token = str(row['token']).strip()
        
        # Skip if token already exists and is not empty
        if current_token and current_token != '' and current_token != 'nan':
            print(f"✅ SKIP: {company_name} → {current_symbol} (Token: {current_token} already exists)")
            continue
        
        print(f"\n🔍 SEARCHING: {company_name} (Symbol: {current_symbol})")
        
        # Method 1: Search by exact company name match
        name_matches = nse_stocks[nse_stocks['SN'].str.upper() == company_name.upper()]
        
        # Method 2: Search by symbol if name match fails
        symbol_matches = nse_stocks[nse_stocks['SC'].str.upper() == current_symbol.upper()]
        
        # Method 3: Search by display symbol (NS column)
        display_matches = nse_stocks[nse_stocks['NS'].str.upper() == current_symbol.upper()]
        
        found_match = None
        search_method = ""
        
        if len(name_matches) > 0:
            found_match = name_matches.iloc[0]
            search_method = "Company Name"
        elif len(symbol_matches) > 0:
            found_match = symbol_matches.iloc[0]
            search_method = "Symbol Code"
        elif len(display_matches) > 0:
            found_match = display_matches.iloc[0]
            search_method = "Display Symbol"
        
        if found_match is not None:
            actual_symbol = found_match['SC']
            token_value = found_match['TK']
            company_from_csv = found_match['SN']
            
            print(f"    ✓ FOUND via {search_method}: {company_from_csv}")
            print(f"    Symbol: {actual_symbol}, Token: {token_value}")
            
            # Update token
            stock_names_df.loc[index, 'token'] = token_value
            tokens_filled.append({
                'company': company_name,
                'symbol': current_symbol,
                'actual_symbol': actual_symbol,
                'token': token_value,
                'method': search_method
            })
            
            # Update symbol if different
            if actual_symbol != current_symbol:
                print(f"    🔄 UPDATING SYMBOL: {current_symbol} → {actual_symbol}")
                stock_names_df.loc[index, 'current_symbol'] = actual_symbol
                updated_symbols.append({
                    'company': company_name,
                    'old_symbol': current_symbol,
                    'new_symbol': actual_symbol,
                    'token': token_value
                })
            
            print(f"    ✅ SUCCESS: Token {token_value} added")
            
        else:
            print(f"    ❌ NOT FOUND: No match in StockScriptNew.csv")
            not_found_stocks.append({
                'company': company_name,
                'symbol': current_symbol
            })
        
        print("-" * 60)
    
    # Save updated CSV with token column
    print(f"\n💾 Saving updated stock_names_symbol.csv with tokens...")
    stock_names_df.to_csv('stock_names_symbol.csv', header=False, index=False)
    
    # Generate summary report
    print("\n📊 SUMMARY REPORT")
    print("=" * 80)
    print(f"Total stocks processed: {len(stock_names_df)}")
    print(f"Symbols updated: {len(updated_symbols)}")
    print(f"Tokens filled: {len(tokens_filled)}")
    print(f"Stocks not found: {len(not_found_stocks)}")
    print(f"Already had tokens: {len(stock_names_df) - len(tokens_filled) - len(not_found_stocks)}")
    
    if updated_symbols:
        print(f"\n✅ UPDATED SYMBOLS ({len(updated_symbols)}):")
        print("-" * 50)
        for update in updated_symbols:
            print(f"  {update['company']}")
            print(f"    {update['old_symbol']} → {update['new_symbol']} (Token: {update['token']})")
    
    if tokens_filled:
        print(f"\n🎯 TOKENS FILLED ({len(tokens_filled)}):")
        print("-" * 50)
        for stock in tokens_filled[:10]:  # Show first 10
            print(f"  {stock['company']} → {stock['actual_symbol']} (Token: {stock['token']}) [via {stock['method']}]")
        if len(tokens_filled) > 10:
            print(f"  ... and {len(tokens_filled) - 10} more")
    
    if not_found_stocks:
        print(f"\n❌ NOT FOUND IN StockScriptNew.csv ({len(not_found_stocks)}):")
        print("-" * 50)
        for stock in not_found_stocks:
            print(f"  {stock['company']} ({stock['symbol']})")
    
    # Save detailed report
    report_filename = 'missing_tokens_report.txt'
    with open(report_filename, 'w') as f:
        f.write("MISSING TOKEN EXTRACTION REPORT\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Total stocks processed: {len(stock_names_df)}\n")
        f.write(f"Symbols updated: {len(updated_symbols)}\n")
        f.write(f"Tokens filled: {len(tokens_filled)}\n")
        f.write(f"Stocks not found: {len(not_found_stocks)}\n")
        f.write(f"Already had tokens: {len(stock_names_df) - len(tokens_filled) - len(not_found_stocks)}\n\n")
        
        if updated_symbols:
            f.write("UPDATED SYMBOLS:\n")
            f.write("-" * 20 + "\n")
            for update in updated_symbols:
                f.write(f"{update['company']}\n")
                f.write(f"  {update['old_symbol']} → {update['new_symbol']} (Token: {update['token']})\n\n")
        
        if tokens_filled:
            f.write("TOKENS FILLED:\n")
            f.write("-" * 20 + "\n")
            for stock in tokens_filled:
                f.write(f"{stock['company']} → {stock['actual_symbol']} (Token: {stock['token']}) [Method: {stock['method']}]\n")
            f.write("\n")
        
        if not_found_stocks:
            f.write("NOT FOUND:\n")
            f.write("-" * 20 + "\n")
            for stock in not_found_stocks:
                f.write(f"{stock['company']} ({stock['symbol']})\n")
    
    print(f"\n📝 Detailed report saved to: {report_filename}")
    print("\n🎉 Missing token extraction process completed!")
    print(f"📄 Updated CSV maintains 3 columns: Company Name, Symbol, Token")

if __name__ == "__main__":
    update_stock_symbols()
