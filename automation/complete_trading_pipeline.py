#!/usr/bin/env python3
"""
Complete Trading System Pipeline

PURPOSE: Complete pipeline that trains ML model and runs trading simulation
WORKFLOW:
1. Train ML model on historical data
2. Save trained model 
3. Run trading simulation using the model
4. Generate comprehensive reports

USAGE: python complete_trading_pipeline.py
"""

import logging
import sys
from pathlib import Path
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('complete_pipeline.log'),
        logging.StreamHandler()
    ]
)

def check_dependencies():
    """Check if required dependencies are available"""
    logger = logging.getLogger(__name__)
    
    missing_deps = []
    
    # Check for sklearn
    try:
        import sklearn
        logger.info(f"✅ scikit-learn {sklearn.__version__} available")
    except ImportError:
        missing_deps.append("scikit-learn")
    
    # Check for pandas/numpy
    try:
        import pandas as pd
        import numpy as np
        logger.info(f"✅ pandas {pd.__version__} available")
    except ImportError:
        missing_deps.append("pandas/numpy")
    
    # Check optional dependencies
    try:
        import xgboost
        logger.info(f"✅ XGBoost {xgboost.__version__} available")
    except ImportError:
        logger.info("⚠️  XGBoost not available (optional)")
    
    try:
        import tensorflow
        logger.info(f"✅ TensorFlow {tensorflow.__version__} available")
    except ImportError:
        logger.info("⚠️  TensorFlow not available (optional)")
    
    if missing_deps:
        logger.error(f"❌ Missing required dependencies: {', '.join(missing_deps)}")
        logger.error("Please install them using: pip install scikit-learn pandas numpy")
        return False
    
    return True

def verify_data_availability():
    """Check if historical data is available"""
    logger = logging.getLogger(__name__)
    
    data_path = Path("data/NSE_AllStocks_historical_data_5min.csv")
    
    if not data_path.exists():
        logger.error(f"❌ Historical data file not found: {data_path}")
        logger.error("Please ensure the NSE_AllStocks_historical_data_5min.csv file is in the data/ directory")
        return False
    
    # Check data quality
    try:
        df = pd.read_csv(data_path, nrows=100)  # Read first 100 rows for quick check
        required_columns = ['exchange_name', 'stock_code', 'date', 'time', 'open', 'high', 'low', 'close', 'volume']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"❌ Missing required columns: {missing_columns}")
            return False
        
        logger.info(f"✅ Data file verified: {len(df)} sample rows loaded")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error reading data file: {e}")
        return False

def train_model():
    """Train the ML model"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting ML model training...")
    
    try:
        # Import and train the model
        from ml_trading_model import train_trading_model
        
        data_path = "data/NSE_AllStocks_historical_data_5min.csv"
        
        # Train Random Forest model (most stable)
        model = train_trading_model(data_path, model_type='random_forest')
        
        logger.info("✅ ML model training completed successfully")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Could not import ML training module: {e}")
        logger.info("💡 Will proceed with basic dummy model")
        return False
    except Exception as e:
        logger.error(f"❌ Model training failed: {e}")
        logger.info("💡 Will proceed with basic dummy model")
        return False

def run_simulation():
    """Run the trading simulation"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting trading simulation...")
    
    try:
        from trading_simulation import TradingSimulator
        
        # Initialize simulator with reasonable capital
        simulator = TradingSimulator(initial_capital=500000)
        
        # Run simulation on first 5 days (for demonstration)
        simulator.run_simulation()
        
        logger.info("✅ Trading simulation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Simulation failed: {e}")
        return False

def main():
    """Main pipeline function"""
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Complete Trading System Pipeline")
    logger.info("=" * 60)
    
    # Step 1: Check dependencies
    if not check_dependencies():
        logger.error("❌ Dependency check failed")
        return False
    
    # Step 2: Verify data availability
    if not verify_data_availability():
        logger.error("❌ Data verification failed")
        return False
    
    # Step 3: Train ML model
    model_trained = train_model()
    if model_trained:
        logger.info("✅ Model training phase completed")
    else:
        logger.warning("⚠️  Model training skipped, will use basic model")
    
    # Step 4: Run simulation
    simulation_success = run_simulation()
    if simulation_success:
        logger.info("✅ Simulation phase completed")
    else:
        logger.error("❌ Simulation failed")
        return False
    
    logger.info("🎉 Complete pipeline executed successfully!")
    logger.info("=" * 60)
    logger.info("📋 Generated Files:")
    logger.info("  - trade_ledger_*.csv: Complete trade history")
    logger.info("  - trading_simulation.log: Detailed simulation logs")
    logger.info("  - model/: Trained ML model files")
    logger.info("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)