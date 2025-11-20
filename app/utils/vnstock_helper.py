import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

def fetch_stock_data(symbol, start_date, end_date, interval='1D'):
    """
    ✅ CORRECT: Use Quote class from vnstock
    
    Args:
        symbol: Stock symbol (e.g., 'VCB', 'VHM')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Time interval - Options:
            - '1D': 1 day (default)
            - '1W': 1 week
            - '1M': 1 month
            - '1H': 1 hour
            - '30m': 30 minutes
            - '15m': 15 minutes
            - '5m': 5 minutes
            - '1m': 1 minute
    
    Returns:
        DataFrame with columns: time/date, open, high, low, close, volume
    """
    try:
        from vnstock import Quote
        
        # ✅ Initialize Quote with symbol and source
        quote = Quote(symbol=symbol, source='VCI')
        
        # ✅ Get historical data with proper interval
        df = quote.history(
            start=start_date,
            end=end_date,
            interval=interval,
            to_df=True  # Return as DataFrame
        )
        
        if df is None or df.empty:
            logger.warning(f"No data for {symbol}")
            return None
        
        # ✅ Standardize column names
        # vnstock returns: time, open, high, low, close, volume
        column_map = {
            'time': 'timestamp',
            'date': 'timestamp',
            # Keep other columns as-is
        }
        
        # Rename if columns exist
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        
        # ✅ Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing column {col} for {symbol}")
                logger.info(f"Available columns: {df.columns.tolist()}")
                return None
        
        # ✅ Set timestamp as index if it exists
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        elif 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
        
        logger.info(f"✓ {symbol}: {len(df)} records from vnstock (interval={interval})")
        return df
        
    except ImportError:
        logger.error("vnstock not installed. Install with: pip install vnstock")
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_price_board(symbols):
    """
    ✅ CORRECT: Get real-time price board using Trading class
    
    Args:
        symbols: List of stock symbols
    
    Returns:
        DataFrame with real-time prices
    """
    try:
        from vnstock import Trading
        
        # ✅ Initialize Trading with source
        trading = Trading(source='VCI')
        
        # ✅ Get price board for all symbols at once
        df = trading.price_board(symbols)
        
        if df is None or df.empty:
            logger.warning(f"No price data for symbols: {symbols}")
            return None
        
        logger.info(f"✓ Got price board for {len(df)} symbols")
        
        # ✅ Standardize column names
        # vnstock may return different column names depending on version
        rename_map = {
            'ticker': 'symbol',
            'lastPrice': 'close',
            'matchedPrice': 'close',
            'referencePrice': 'refPrice',
            'openPrice': 'open',
            'highestPrice': 'high',
            'lowestPrice': 'low',
            'totalVolume': 'volume'
        }
        
        # Only rename columns that exist
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        if cols_to_rename:
            df = df.rename(columns=cols_to_rename)
        
        return df
        
    except ImportError:
        logger.error("vnstock not installed")
        return None
    except Exception as e:
        logger.error(f"Error in get_price_board: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def list_all_symbols():
    """
    ✅ CORRECT: List all symbols using Listing class
    """
    try:
        from vnstock import Listing
        
        listing = Listing()
        df = listing.all_symbols()
        
        if df is None or df.empty:
            logger.warning("No symbols found")
            return None
        
        logger.info(f"✓ Listed {len(df)} symbols")
        return df
        
    except ImportError:
        logger.error("vnstock not installed")
        return None
    except Exception as e:
        logger.error(f"Error listing symbols: {e}")
        return None
