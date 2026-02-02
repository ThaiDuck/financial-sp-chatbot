import logging
from datetime import datetime
import pandas as pd
import time
import asyncio
from threading import Lock
from functools import wraps

logger = logging.getLogger(__name__)

# ✅ RATE LIMITER: 20 requests per minute = 1 request per 3 seconds (safe margin)
class VNStockRateLimiter:
    """Thread-safe rate limiter for vnstock API (20 req/min)"""
    
    def __init__(self, max_requests: int = 18, time_window: int = 60):
        """
        Args:
            max_requests: Max requests per time window (18 to be safe, limit is 20)
            time_window: Time window in seconds (60 = 1 minute)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []  # List of timestamps
        self.lock = Lock()
        self.min_interval = time_window / max_requests  # ~3.33 seconds between requests
    
    def wait_if_needed(self) -> float:
        """
        Wait if rate limit would be exceeded.
        Returns: Time waited in seconds
        """
        with self.lock:
            now = time.time()
            
            # Remove old requests outside time window
            self.requests = [t for t in self.requests if now - t < self.time_window]
            
            # Check if we need to wait
            if len(self.requests) >= self.max_requests:
                # Wait until oldest request expires
                oldest = min(self.requests)
                wait_time = self.time_window - (now - oldest) + 0.5  # Extra 0.5s buffer
                
                if wait_time > 0:
                    logger.warning(f"⏳ VNStock rate limit: waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    now = time.time()
                    # Clean up again after waiting
                    self.requests = [t for t in self.requests if now - t < self.time_window]
            
            # Also enforce minimum interval between requests
            if self.requests:
                last_request = max(self.requests)
                time_since_last = now - last_request
                
                if time_since_last < self.min_interval:
                    sleep_time = self.min_interval - time_since_last
                    time.sleep(sleep_time)
                    now = time.time()
            
            # Record this request
            self.requests.append(now)
            
            return 0
    
    def get_status(self) -> dict:
        """Get current rate limit status"""
        with self.lock:
            now = time.time()
            self.requests = [t for t in self.requests if now - t < self.time_window]
            
            return {
                "requests_used": len(self.requests),
                "requests_remaining": self.max_requests - len(self.requests),
                "reset_in": self.time_window - (now - min(self.requests)) if self.requests else 0
            }


# Global rate limiter instance
_rate_limiter = VNStockRateLimiter(max_requests=18, time_window=60)


def rate_limited(func):
    """Decorator to apply rate limiting to vnstock functions"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        _rate_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper


def retry_on_error(max_retries: int = 3, delay: float = 5.0):
    """Decorator to retry on error with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check if it's a rate limit error
                    if "rate" in error_msg or "limit" in error_msg or "429" in error_msg or "too many" in error_msg:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"⚠️ VNStock rate limit hit, retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        # Other errors, shorter wait
                        logger.warning(f"⚠️ VNStock error: {e}, retry {attempt + 1}/{max_retries}...")
                        time.sleep(delay)
            
            # All retries failed
            logger.error(f"❌ VNStock failed after {max_retries} retries: {last_error}")
            return None
        return wrapper
    return decorator


@retry_on_error(max_retries=3, delay=5.0)
@rate_limited
def fetch_stock_data(symbol, start_date, end_date, interval='1D'):
    """
    ✅ RATE LIMITED + RETRY: Fetch stock data with protection
    
    Args:
        symbol: Stock symbol (e.g., 'VCB', 'VHM')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Time interval ('1D', '1W', '1M', '1H', '30m', '15m', '5m', '1m')
    
    Returns:
        DataFrame with columns: time/date, open, high, low, close, volume
    """
    try:
        from vnstock import Vnstock
        
        logger.info(f"📊 Fetching {symbol} ({start_date} to {end_date}, interval={interval})")
        
        # ✅ Initialize Vnstock
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        
        # ✅ Get historical data
        df = stock.quote.history(
            start=start_date,
            end=end_date,
            interval=interval
        )
        
        if df is None or df.empty:
            logger.warning(f"No data for {symbol}")
            return None
        
        # ✅ Standardize column names
        column_map = {
            'time': 'timestamp',
            'date': 'timestamp',
        }
        
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        
        # ✅ Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing column {col} for {symbol}")
                logger.info(f"Available columns: {df.columns.tolist()}")
                return None
        
        # ✅ Set timestamp as index
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        elif 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
        
        logger.info(f"✓ {symbol}: {len(df)} records (interval={interval})")
        return df
        
    except ImportError:
        logger.error("vnstock not installed. Install with: pip install vnstock")
        return None
    except Exception as e:
        # Re-raise to trigger retry
        raise e


@retry_on_error(max_retries=3, delay=5.0)
@rate_limited
def get_price_board(symbols):
    """
    ✅ RATE LIMITED + RETRY: Get real-time price board
    
    Args:
        symbols: List of stock symbols
    
    Returns:
        DataFrame with real-time prices
    """
    try:
        from vnstock import Vnstock
        
        if not symbols:
            return None
        
        logger.info(f"📊 Getting price board for {symbols}")
        
        # ✅ Initialize Vnstock
        stock = Vnstock().stock(symbol=symbols[0], source='VCI')
        
        # ✅ Get price board
        df = stock.trading.price_board(symbols)
        
        if df is None or df.empty:
            logger.warning(f"No price data for symbols: {symbols}")
            return None
        
        logger.info(f"✓ Got price board for {len(df)} symbols")
        
        # ✅ Standardize column names
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
        
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        if cols_to_rename:
            df = df.rename(columns=cols_to_rename)
        
        return df
        
    except ImportError:
        logger.error("vnstock not installed")
        return None
    except Exception as e:
        # Re-raise to trigger retry
        raise e


@retry_on_error(max_retries=2, delay=3.0)
@rate_limited
def list_all_symbols():
    """
    ✅ RATE LIMITED + RETRY: List all symbols
    """
    try:
        from vnstock import Vnstock
        
        logger.info("📊 Listing all symbols...")
        
        stock = Vnstock()
        df = stock.stock().listing.all_symbols()
        
        if df is None or df.empty:
            logger.warning("No symbols found")
            return None
        
        logger.info(f"✓ Listed {len(df)} symbols")
        return df
        
    except ImportError:
        logger.error("vnstock not installed")
        return None
    except Exception as e:
        raise e


def get_rate_limit_status() -> dict:
    """Get current rate limit status for monitoring"""
    return _rate_limiter.get_status()


# ✅ BATCH HELPER: Fetch multiple symbols with rate limiting
def fetch_multiple_stocks_safe(symbols: list, start_date: str, end_date: str, interval: str = '1D') -> dict:
    """
    Safely fetch multiple stocks with built-in rate limiting.
    Returns dict of {symbol: DataFrame}
    """
    results = {}
    
    for symbol in symbols:
        try:
            df = fetch_stock_data(symbol, start_date, end_date, interval)
            if df is not None:
                results[symbol] = df
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            continue
    
    return results
