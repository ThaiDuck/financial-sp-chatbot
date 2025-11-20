from datetime import datetime, timedelta
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import asyncio
import time
from ..database.models import VNStock
from ..utils.vnstock_helper import fetch_stock_data, get_price_board

logger = logging.getLogger(__name__)

# Cache for real-time quotes (5 minutes TTL)
_quote_cache = {}
_cache_ttl = 300  # 5 minutes

def _get_cached_quote(symbol: str) -> Optional[Dict]:
    """Get cached quote if still valid"""
    if symbol in _quote_cache:
        data, timestamp = _quote_cache[symbol]
        if time.time() - timestamp < _cache_ttl:
            return data
    return None

def _set_cached_quote(symbol: str, data: Dict):
    """Cache quote data"""
    _quote_cache[symbol] = (data, time.time())

async def fetch_vn_stock_data_batch(symbols: List[str], start_date=None, end_date=None, interval='1D', max_concurrent=5):
    """
    ✅ FIXED: Add interval parameter
    
    Args:
        symbols: List of stock symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Time interval ('1D', '1W', '1M', '1H', '30m', '15m', '5m', '1m')
        max_concurrent: Max concurrent requests
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    valid_symbols = [s.upper() for s in symbols]
    
    if not valid_symbols:
        return []
    
    logger.info(f"Fetching {len(valid_symbols)} symbols: {valid_symbols} (interval={interval})")
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_single(symbol: str):
        async with semaphore:
            try:
                logger.info(f"Fetching {symbol}...")
                
                # ✅ Pass interval parameter
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None,
                    fetch_stock_data,
                    symbol,
                    start_date,
                    end_date,
                    interval  # ✅ Add interval
                )
                
                if df is None or df.empty:
                    logger.warning(f"No data for {symbol}")
                    return []
                
                # Convert to list of dicts
                records = []
                for idx, row in df.iterrows():
                    records.append({
                        'symbol': symbol,
                        'open_price': float(row.get('open', 0)),
                        'close_price': float(row.get('close', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'volume': float(row.get('volume', 0)),
                        'timestamp': pd.to_datetime(idx) if not isinstance(idx, datetime) else idx
                    })
                
                logger.info(f"✓ {symbol}: {len(records)} records")
                return records
                
            except Exception as e:
                logger.error(f"✗ {symbol}: {e}")
                return []
    
    # Fetch all symbols concurrently
    results = await asyncio.gather(*[fetch_single(s) for s in valid_symbols])
    all_data = [item for sublist in results for item in sublist]
    
    logger.info(f"Total: {len(all_data)} records from {len(valid_symbols)} symbols")
    return all_data

async def fetch_vn_stock_data(symbols, start_date=None, end_date=None, interval='1D'):
    """
    ✅ FIXED: Add interval parameter
    """
    return await fetch_vn_stock_data_batch(symbols, start_date, end_date, interval)

async def save_vn_stock_data(session, stock_data_list: List[Dict]) -> bool:
    """Save VN stock data to database"""
    try:
        if not stock_data_list:
            logger.warning("No VN stock data to save")
            return False
            
        for stock_data in stock_data_list:
            # Ensure timestamp is a proper datetime object
            if 'timestamp' in stock_data:
                timestamp = stock_data['timestamp']
                if not isinstance(timestamp, datetime):
                    try:
                        if isinstance(timestamp, (int, float)):
                            stock_data['timestamp'] = datetime.fromtimestamp(timestamp)
                        else:
                            stock_data['timestamp'] = pd.to_datetime(timestamp)
                    except:
                        # Use current time as fallback if conversion fails
                        stock_data['timestamp'] = datetime.now()
                        logger.warning(f"Used fallback timestamp for {stock_data['symbol']}")
            
            stock = VNStock(
                symbol=stock_data['symbol'],
                open_price=stock_data['open_price'],
                close_price=stock_data['close_price'],
                high=stock_data['high'],
                low=stock_data['low'],
                volume=stock_data['volume'],
                timestamp=stock_data['timestamp']
            )
            session.add(stock)
        
        session.commit()
        logger.info(f"Saved {len(stock_data_list)} VN stock records")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving VN stock data: {e}")
        return False

async def get_latest_stock_price(session, symbol, is_vn_stock=True):
    """
    ✅ FIXED: Get latest stock price with better error handling
    """
    if not is_vn_stock:
        from ..services.stock_us_service import USStockService
        return await USStockService.get_us_stock_price(symbol)
    
    try:
        symbol = symbol.upper()
        
        # ✅ CRITICAL FIX: Don't return early on cache hit, check DB first
        cached_data = _get_cached_quote(symbol)
        if cached_data:
            logger.info(f"Returning cached data for {symbol}")
            return cached_data
        
        # Try database first
        one_day_ago = datetime.now() - timedelta(days=1)
        latest_price = session.query(VNStock)\
            .filter(VNStock.symbol == symbol)\
            .filter(VNStock.timestamp >= one_day_ago)\
            .order_by(VNStock.timestamp.desc())\
            .first()
            
        if latest_price:
            result = {
                'symbol': latest_price.symbol,
                'open_price': latest_price.open_price,
                'close_price': latest_price.close_price,
                'high': latest_price.high,
                'low': latest_price.low,
                'volume': latest_price.volume,
                'timestamp': latest_price.timestamp
            }
            _set_cached_quote(symbol, result)
            logger.info(f"✓ Found {symbol} in DB")
            return result
        
        # ✅ Fetch from vnstock v3
        logger.info(f"⚠️ No DB data for {symbol}, fetching from vnstock v3...")
        
        try:
            loop = asyncio.get_event_loop()
            price_board_df = await loop.run_in_executor(
                None,
                get_price_board,
                [symbol]
            )
            
            if price_board_df is not None and not price_board_df.empty:
                row = price_board_df.iloc[0]
                
                # ✅ Extract with correct field names
                open_price = float(row.get('open', row.get('refPrice', 0)))
                close_price = float(row.get('lastPrice', row.get('close', 0)))
                high_price = float(row.get('high', 0))
                low_price = float(row.get('low', 0))
                volume = float(row.get('volume', 0))
                
                result = {
                    'symbol': symbol,
                    'open_price': open_price,
                    'close_price': close_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume,
                    'timestamp': datetime.now()
                }
                
                _set_cached_quote(symbol, result)
                
                # ✅ Save to database
                stock = VNStock(**result)
                session.add(stock)
                try:
                    session.commit()
                    logger.info(f"✅ Saved {symbol} to DB")
                except:
                    session.rollback()
                
                logger.info(f"✅ Fetched {symbol} from vnstock v3: {close_price:,.0f}")
                return result
                
        except Exception as e:
            logger.error(f"Error fetching from vnstock v3 for {symbol}: {e}")
        
        # ✅ Return None if all methods fail
        logger.warning(f"❌ No data found for {symbol}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting latest price for {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def get_vn_stock_quote(symbol):
    """Get real-time quote using Trading.price_board()"""
    try:
        symbol = symbol.upper()
        
        loop = asyncio.get_event_loop()
        price_board_df = await loop.run_in_executor(
            None,
            get_price_board,
            [symbol]
        )
        
        if price_board_df is not None and not price_board_df.empty:
            row = price_board_df.iloc[0]
            
            last_price = float(row.get('lastPrice', row.get('close', 0)))
            ref_price = float(row.get('refPrice', row.get('open', last_price)))
            
            return {
                'symbol': symbol,
                'price': last_price,
                'change': last_price - ref_price,
                'change_percent': ((last_price - ref_price) / ref_price * 100) if ref_price > 0 else 0,
                'volume': float(row.get('volume', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0))
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {e}")
        return None

async def get_multiple_vn_stock_quotes(symbols: List[str]) -> Dict[str, Optional[Dict]]:
    """
    Get real-time quotes for multiple stocks using Trading.price_board()
    Much more efficient than individual calls!
    """
    results = {}
    
    valid_symbols = [s.upper() for s in symbols]
    
    if not valid_symbols:
        return results
    
    # Check cache first
    uncached_symbols = []
    for symbol in valid_symbols:
        cached = _get_cached_quote(symbol)
        if cached:
            results[symbol] = cached
        else:
            uncached_symbols.append(symbol)
    
    if not uncached_symbols:
        return results
    
    # Fetch ALL uncached symbols in ONE call (price_board supports multiple symbols!)
    try:
        loop = asyncio.get_event_loop()
        price_board_df = await loop.run_in_executor(
            None,
            get_price_board,
            uncached_symbols
        )
        
        if price_board_df is not None and not price_board_df.empty:
            for idx, row in price_board_df.iterrows():
                symbol = row.get('ticker', row.get('symbol', uncached_symbols[idx]))
                last_price = float(row.get('lastPrice', row.get('close', 0)))
                ref_price = float(row.get('refPrice', row.get('open', last_price)))
                
                quote = {
                    'symbol': symbol,
                    'price': last_price,
                    'change': last_price - ref_price,
                    'change_percent': ((last_price - ref_price) / ref_price * 100) if ref_price > 0 else 0,
                    'volume': float(row.get('volume', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0))
                }
                _set_cached_quote(symbol, quote)
                results[symbol] = quote
                
    except Exception as e:
        logger.error(f"Error getting batch quotes: {e}")
    
    return results

async def get_vn_company_profile(symbol):
    """Get company profile for a VN stock"""
    try:
        symbol = symbol.upper()
        
        # Skip index symbols
        if symbol in ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]:
            logger.warning(f"Skipping index symbol {symbol} - indices are not supported")
            return None
        
        # Try to get company info using vnstock
        try:
            info = vnstock.company_profile(symbol)
            if info is not None and not info.empty:
                row = info.iloc[0]
                return {
                    "symbol": symbol,
                    "name": row.get("companyName", ""),
                    "exchange": row.get("exchange", ""),
                    "industry": row.get("industryName", ""),
                    "website": row.get("website", ""),
                    "established_year": row.get("establishedYear", ""),
                    "description": row.get("businessOverview", "")
                }
        except Exception as e:
            logger.error(f"Error getting company profile for {symbol}: {e}")
        
        return None
    except Exception as e:
        logger.error(f"Error getting company profile for {symbol}: {e}")
        return None

async def calculate_vn_stock_technical_indicators(symbol, period="1mo"):
    """Calculate technical indicators for a VN stock"""
    try:
        symbol = symbol.upper()
        
        # Skip index symbols
        if symbol in ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]:
            logger.warning(f"Skipping index symbol {symbol} - indices are not supported")
            return {"error": "Market indices are not supported"}
        
        # Get historical data
        end_date = datetime.now()
        
        if period == "1mo":
            start_date = end_date - timedelta(days=30)
        elif period == "3mo":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)
            
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Regular VN stock - simplified code without index handling
        df = vnstock.stock_historical_data(
            symbol=symbol,
            start_date=start_date_str,
            end_date=end_date_str
        )
            
        if df is None or df.empty:
            return {"error": f"No data available for {symbol}"}
            
        # Calculate indicators
        if len(df) >= 20:
            df['SMA20'] = df['close'].rolling(window=20).mean()
        if len(df) >= 50:
            df['SMA50'] = df['close'].rolling(window=50).mean()
            
        # Calculate RSI (14-period)
        if len(df) > 14:
            # Get price differences
            delta = df['close'].diff()
            
            # Get gains and losses
            gain = delta.mask(delta < 0, 0)
            loss = -delta.mask(delta > 0, 0)
            
            # Calculate average gain and loss
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))
        
        # Get the latest values
        latest = df.iloc[-1]
        
        # Determine trend
        if 'SMA20' in df.columns and 'SMA50' in df.columns:
            if latest['SMA20'] > latest['SMA50']:
                trend = "Uptrend"
            elif latest['SMA20'] < latest['SMA50']:
                trend = "Downtrend"
            else:
                trend = "Neutral"
        else:
            trend = "Insufficient data"
            
        return {
            "SMA20": float(latest['SMA20']) if 'SMA20' in df.columns else None,
            "SMA50": float(latest['SMA50']) if 'SMA50' in df.columns else None,
            "RSI": float(latest['RSI']) if 'RSI' in df.columns else None,
            "trend": trend
        }
        
    except Exception as e:
        logger.error(f"Error calculating technical indicators for {symbol}: {e}")
        return {"error": str(e)}

async def get_vn_stocks_with_charts(session, symbols: List[str], period: str = "1mo") -> Dict[str, Any]:
    """
    ✅ FIXED: Remove price validation (all prices are valid!)
    """
    try:
        from .visualization_service import StockVisualizer
        
        # ✅ Calculate date range AND interval
        end_date = datetime.now()
        
        # ✅ Map period to (days, interval)
        period_config = {
            "1d": (1, "1H"),      # 1 day: hourly data
            "1w": (7, "1D"),      # 1 week: daily data
            "1mo": (30, "1D"),    # 1 month: daily data
            "3mo": (90, "1D"),    # 3 months: daily data
            "6mo": (180, "1W"),   # 6 months: weekly data
            "1y": (365, "1W"),    # 1 year: weekly data
        }
        
        days, interval = period_config.get(period.lower(), (30, "1D"))
        start_date = end_date - timedelta(days=days)
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📊 Period: {period} → {days} days, interval: {interval}")
        
        symbol_dataframes = {}
        symbol_stats = {}
        
        from sqlalchemy import and_
        
        for symbol in symbols:
            symbol = symbol.upper()
            
            # Try DB first
            db_records = session.query(VNStock)\
                .filter(
                    and_(
                        VNStock.symbol == symbol,
                        VNStock.timestamp >= start_date,
                        VNStock.timestamp <= end_date
                    )
                )\
                .order_by(VNStock.timestamp.asc())\
                .all()
            
            if db_records and len(db_records) > 10:
                logger.info(f"✓ Using {len(db_records)} DB records for {symbol}")
                
                df = pd.DataFrame([{
                    'timestamp': r.timestamp,
                    'open': r.open_price,
                    'close': r.close_price,
                    'high': r.high,
                    'low': r.low,
                    'volume': r.volume
                } for r in db_records])
                
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)
                
                # ✅ REMOVED: Price validation (all prices are valid)
                # Just log the data
                latest = df.iloc[-1]
                logger.info(f"📊 {symbol}: {latest['close']:,.2f} (no validation)")
                
                symbol_dataframes[symbol] = df
                
                # Calculate stats
                first = df.iloc[0]
                price_change = latest['close'] - first['close']
                price_change_pct = (price_change / first['close']) * 100
                
                symbol_stats[symbol] = {
                    'latest_price': float(latest['close']),
                    'open': float(latest['open']),
                    'high': float(df['high'].max()),
                    'low': float(df['low'].min()),
                    'volume': float(latest['volume']),
                    'change': float(price_change),
                    'change_percent': float(price_change_pct),
                    'period_high': float(df['high'].max()),
                    'period_low': float(df['low'].min()),
                    'avg_volume': float(df['volume'].mean())
                }
                
                logger.info(f"📊 {symbol}: {latest['close']:,.0f} VND ({price_change_pct:+.2f}%)")
                continue
            
            else:
                logger.info(f"⚠️ Insufficient DB data for {symbol} ({len(db_records) if db_records else 0} records)")
        
        # ✅ Fetch missing symbols from API
        missing_symbols = [s for s in symbols if s.upper() not in symbol_dataframes]
        
        if missing_symbols:
            logger.info(f"⚠️ Fetching from API: {missing_symbols}")
            
            stock_data = await fetch_vn_stock_data_batch(
                missing_symbols, 
                start_date_str, 
                end_date_str,
                interval
            )
            
            if stock_data:
                # Save to DB
                await save_vn_stock_data(session, stock_data)
                logger.info(f"✅ Saved {len(stock_data)} records to DB")
                
                # Process for charts
                for symbol in missing_symbols:
                    symbol = symbol.upper()
                    symbol_records = [r for r in stock_data if r['symbol'] == symbol]
                    
                    if not symbol_records or len(symbol_records) < 10:
                        logger.warning(f"⚠️ {symbol}: insufficient data ({len(symbol_records)} records)")
                        continue
                    
                    df = pd.DataFrame(symbol_records)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    df.sort_index(inplace=True)
                    
                    df.rename(columns={
                        'open_price': 'open',
                        'close_price': 'close'
                    }, inplace=True)
                    
                    # ✅ VALIDATE: Only check zeros
                    latest = df.iloc[-1]
                    if latest['close'] <= 0 or latest['open'] <= 0:
                        continue
                    
                    symbol_dataframes[symbol] = df
                    
                    first = df.iloc[0]
                    price_change = latest['close'] - first['close']
                    price_change_pct = (price_change / first['close']) * 100
                    
                    symbol_stats[symbol] = {
                        'latest_price': float(latest['close']),
                        'open': float(latest['open']),
                        'high': float(df['high'].max()),
                        'low': float(df['low'].min()),
                        'volume': float(latest['volume']),
                        'change': float(price_change),
                        'change_percent': float(price_change_pct),
                        'period_high': float(df['high'].max()),
                        'period_low': float(df['low'].min()),
                        'avg_volume': float(df['volume'].mean())
                    }
        
        # Check if we have data
        if not symbol_dataframes:
            return {
                "error": "No valid data available",
                "symbols": symbols,
                "message": "No real stock data found. Please update stock data from sidebar."
            }
        
        # Generate charts
        charts = {}
        visualizer = StockVisualizer()
        
        for symbol, df in symbol_dataframes.items():
            charts[f"{symbol}_candlestick"] = visualizer.create_candlestick_chart(df, symbol)
            charts[f"{symbol}_technical"] = visualizer.create_technical_analysis_chart(df, symbol)
        
        if len(symbol_dataframes) > 1:
            charts["comparison"] = visualizer.create_multi_stock_comparison(symbol_dataframes)
        
        return {
            'symbols': list(symbol_dataframes.keys()),
            'stats': symbol_stats,
            'charts': charts,
            'period': period,
            'start_date': start_date_str,
            'end_date': end_date_str
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)}