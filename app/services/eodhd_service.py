"""
EODHD API Service
✅ Optimized for minimal API calls:
- Batch requests (multi-symbol in 1 call)
- Local caching (24h TTL for EOD data)
- Daily snapshots
"""
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pathlib import Path
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

from ..config import EODHD_API_KEY, EODHD_BASE_URL

CACHE_DIR = Path("cache/eodhd")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 86400
FAILED_CACHE_TTL = 1800

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, timeout=None, *args, **kwargs):
        self.timeout = timeout
        super().__init__(*args, **kwargs)
    
    def send(self, request, **kwargs):
        if kwargs.get('timeout') is None and self.timeout is not None:
            kwargs['timeout'] = self.timeout
        return super().send(request, **kwargs)

def _get_requests_session():
    session = requests.Session()
    
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    
    adapter = TimeoutHTTPAdapter(
        timeout=(10, 90),
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=20
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

_http_session = _get_requests_session()

class EODHDService:
    
    @staticmethod
    def _get_cache_path(ticker: str, date: str = None) -> Path:
        if date:
            return CACHE_DIR / f"{ticker}_{date}.json"
        return CACHE_DIR / f"{ticker}_latest.json"
    
    @staticmethod
    def _is_cache_valid(cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        return age < CACHE_TTL
    
    @staticmethod
    def _read_cache(cache_path: Path) -> Optional[Dict]:
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except:
            return None
    
    @staticmethod
    def _write_cache(cache_path: Path, data: Dict):
        try:
            def convert_timestamps(obj):
                if isinstance(obj, dict):
                    return {k: convert_timestamps(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_timestamps(item) for item in obj]
                elif hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                else:
                    return obj
            
            data_clean = convert_timestamps(data)
            
            with open(cache_path, 'w') as f:
                json.dump(data_clean, f)
        except Exception as e:
            logger.error(f"Cache write failed: {e}")
    
    @staticmethod
    async def get_eod_data(
        ticker: str,
        exchange: str = "US",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        period: str = "d"
    ) -> Optional[pd.DataFrame]:
        try:
            symbol_full = f"{ticker}.{exchange}"
            
            cache_key = f"{symbol_full}_{from_date}_{to_date}_{period}"
            cache_path = CACHE_DIR / f"{cache_key}.json"
            
            if EODHDService._is_cache_valid(cache_path):
                logger.info(f"Cache hit: {ticker}")
                cached = EODHDService._read_cache(cache_path)
                if cached:
                    # ✅ CRITICAL FIX: Ensure cached data has proper DatetimeIndex
                    df = pd.DataFrame(cached)
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df = df.set_index('timestamp')
                        df = df.sort_index()
                        return df[['open', 'high', 'low', 'close', 'volume']]
                    else:
                        logger.warning(f"⚠️ Cached data missing timestamp column, refetching...")
            
            failed_cache_path = CACHE_DIR / f"{cache_key}_failed.txt"
            if failed_cache_path.exists():
                age = time.time() - failed_cache_path.stat().st_mtime
                if age < FAILED_CACHE_TTL:
                    logger.warning(f"Recently failed for {ticker} ({int(age)}s ago), skipping")
                    return None
            
            logger.info(f"Fetching {ticker} from EODHD API...")
            
            url = f"{EODHD_BASE_URL}/eod/{symbol_full}"
            
            params = {
                "api_token": EODHD_API_KEY,
                "fmt": "json",
                "period": period,
                "order": "d"
            }
            
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            try:
                response = _http_session.get(url, params=params, timeout=(10, 90))
                
                if response.status_code != 200:
                    logger.error(f"EODHD error {response.status_code} for {ticker}")
                    failed_cache_path.touch()
                    return None
                
                data = response.json()
                
                if not data or not isinstance(data, list):
                    logger.warning(f"No data for {ticker}")
                    failed_cache_path.touch()
                    return None
                
                if len(data) > 0:
                    logger.info(f"📦 {ticker} raw data sample: {data[0]}")
                    logger.info(f"   Total records: {len(data)}")
                
                df = pd.DataFrame(data)
                
                logger.info(f"📋 {ticker} DataFrame columns: {df.columns.tolist()}")
                logger.info(f"   DataFrame shape: {df.shape}")
                
                # ✅ CRITICAL FIX: Check if 'date' column exists and contains valid dates
                if 'date' not in df.columns:
                    logger.error(f"❌ {ticker}: Missing 'date' column! Columns: {df.columns.tolist()}")
                    failed_cache_path.touch()
                    return None
                
                logger.info(f"   Raw date column sample: {df['date'].head(2).tolist()}")
                logger.info(f"   Date column dtype BEFORE conversion: {df['date'].dtype}")
                
                # ✅ CRITICAL FIX: Convert 'date' to datetime with explicit format
                try:
                    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
                except Exception as dt_error:
                    logger.error(f"❌ {ticker}: Datetime conversion failed: {dt_error}")
                    # Try without format
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                
                # ✅ VALIDATE: Check for NaT (not a time) values
                nat_count = df['date'].isna().sum()
                if nat_count > 0:
                    logger.warning(f"⚠️ {ticker}: {nat_count} invalid dates found, dropping...")
                    df = df.dropna(subset=['date'])
                
                if df.empty:
                    logger.error(f"❌ {ticker}: All dates invalid after conversion")
                    failed_cache_path.touch()
                    return None
                
                logger.info(f"📅 {ticker} after datetime conversion:")
                logger.info(f"   Date dtype: {df['date'].dtype}")
                logger.info(f"   First date: {df['date'].iloc[0]}")
                logger.info(f"   Last date: {df['date'].iloc[-1]}")
                
                # ✅ CRITICAL FIX: Rename BEFORE setting index
                df = df.rename(columns={
                    'date': 'timestamp',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'adjusted_close': 'adj_close',
                    'volume': 'volume'
                })
                
                # ✅ CRITICAL FIX: Set index with explicit copy
                df = df.set_index('timestamp', drop=True)
                df = df.sort_index()
                
                # ✅ VALIDATE: Final index check
                logger.info(f"✅ {ticker} final DataFrame:")
                logger.info(f"   Index type: {type(df.index).__name__}")
                logger.info(f"   Index dtype: {df.index.dtype}")
                logger.info(f"   Index name: {df.index.name}")
                logger.info(f"   Index range: {df.index[0]} to {df.index[-1]}")
                logger.info(f"   Index[0] year: {df.index[0].year}")
                
                # ✅ CRITICAL: Double-check the year
                if df.index[0].year < 2000:
                    logger.error(f"❌ {ticker}: Index year {df.index[0].year} < 2000 - DATA CORRUPTION!")
                    logger.error(f"   Raw index values: {df.index[:5].tolist()}")
                    failed_cache_path.touch()
                    return None
                
                logger.info(f"   Price range: ${df['close'].min():.2f} to ${df['close'].max():.2f}")
                
                # ✅ Cache with proper structure
                cache_data = df.reset_index().to_dict('records')
                EODHDService._write_cache(cache_path, cache_data)
                
                if failed_cache_path.exists():
                    failed_cache_path.unlink()
                
                logger.info(f"EODHD: {ticker} = {len(df)} records")
                
                # ✅ RETURN: Only required columns with proper DatetimeIndex
                return df[['open', 'high', 'low', 'close', 'volume']]
                
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout for {ticker} (90s): {e}")
                failed_cache_path.touch()
                return None
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {ticker}: {e}")
                failed_cache_path.touch()
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error for {ticker}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    async def get_batch_latest_eod(
        symbols: List[str],
        exchange: str = "US"
    ) -> Dict[str, Optional[Dict]]:
        try:
            results = {}
            uncached_symbols = []
            
            for symbol in symbols:
                cache_path = EODHDService._get_cache_path(f"{symbol}.{exchange}")
                
                if EODHDService._is_cache_valid(cache_path):
                    cached = EODHDService._read_cache(cache_path)
                    if cached:
                        results[symbol] = cached
                        continue
                
                uncached_symbols.append(symbol)
            
            if not uncached_symbols:
                logger.info(f"All {len(symbols)} symbols from cache")
                return results
            
            logger.info(f"Batch API call for {len(uncached_symbols)} symbols")
            
            url = f"{EODHD_BASE_URL}/eod-bulk-last-day/{exchange}"
            
            params = {
                "api_token": EODHD_API_KEY,
                "fmt": "json",
                "symbols": ",".join(uncached_symbols)
            }
            
            try:
                response = _http_session.get(url, params=params, timeout=(15, 120))
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for item in data:
                        code = item.get('code', '')
                        
                        if code in uncached_symbols:
                            price_data = {
                                'symbol': code,
                                'price': float(item.get('close', 0)),
                                'open': float(item.get('open', 0)),
                                'high': float(item.get('high', 0)),
                                'low': float(item.get('low', 0)),
                                'close': float(item.get('close', 0)),
                                'volume': float(item.get('volume', 0)),
                                'date': item.get('date'),
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            results[code] = price_data
                            
                            cache_path = EODHDService._get_cache_path(f"{code}.{exchange}")
                            EODHDService._write_cache(cache_path, price_data)
                    
                    logger.info(f"Batch: {len(results)} symbols")
                
            except requests.exceptions.Timeout:
                logger.error("Batch API timeout (120s) - skipping")
            
            for symbol in uncached_symbols:
                if symbol not in results:
                    results[symbol] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Batch EOD error: {e}")
            return {symbol: None for symbol in symbols}
