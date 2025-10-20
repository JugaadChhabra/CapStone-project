# Trading Bot Configuration
# Edit these settings to customize your trading strategy

# POSITION MANAGEMENT
MAX_POSITIONS = 5           # Maximum number of concurrent trades
POSITION_SIZE = 1000        # Position size in rupees per trade
MIN_QUANTITY = 1            # Minimum quantity per trade

# RISK MANAGEMENT  
STOP_LOSS_PERCENT = 2.0     # Stop loss percentage (2% default)
TARGET_PROFIT_PERCENT = 4.0 # Target profit percentage (4% default)

# MARKET TIMING
MARKET_OPEN_TIME = "09:15"  # Market open time (IST)
MARKET_CLOSE_TIME = "15:30" # Market close time (IST)  
STRATEGY_START_TIME = "09:20" # When to start looking for trades

# MONITORING
POSITION_CHECK_INTERVAL = 10 # How often to check positions (seconds)
LOG_LEVEL = "INFO"          # Logging level: DEBUG, INFO, WARNING, ERROR

# STRATEGY PARAMETERS
MINIMUM_MOVE_PERCENT = 2.0  # Minimum percentage move to consider
MOMENTUM_WAIT_TIME = 10.0   # Wait time for momentum check (seconds)
OI_THRESHOLD_PERCENT = 7.0  # OI change threshold percentage

# SAFETY FEATURES
AUTO_CLOSE_AT_MARKET_CLOSE = True  # Close all positions at market close
EMERGENCY_STOP_LOSS = 5.0          # Emergency stop if total loss exceeds this %
MAX_DAILY_LOSS = 5000              # Maximum daily loss in rupees

# ADVANCED SETTINGS
RETRY_FAILED_ORDERS = True         # Retry failed order placements
MAX_ORDER_RETRIES = 3              # Maximum retries for failed orders
ORDER_RETRY_DELAY = 30             # Delay between retries (seconds)

# NOTIFICATION SETTINGS (for future enhancement)
SEND_SMS_ALERTS = False            # Send SMS for important events
SEND_EMAIL_SUMMARY = False         # Send email with daily summary
TELEGRAM_NOTIFICATIONS = False     # Send Telegram notifications