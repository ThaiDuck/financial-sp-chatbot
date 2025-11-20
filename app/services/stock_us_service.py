import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pandas as pd
import time
import asyncio

logger = logging.getLogger(__name__)

from ..services.eodhd_service import EODHDService

# Cache for quotes
_us_quote_cache = {}
_cache_ttl = 300 

def _get_cached_us_quote(symbol: str) -> Optional[Dict]:
    """Get cached US stock quote"""
    if symbol in _us_quote_cache:
        data, timestamp = _us_quote_cache[symbol]
        if time.time() - timestamp < _cache_ttl:
            return data
    return None

def _set_cached_us_quote(symbol: str, data: Dict):
    """Cache US stock quote"""
    _us_quote_cache[symbol] = (data, time.time())

class USStockService:
    """
    ✅ OPTIMIZED: US Stock service using EODHD API
    - Batch requests (many symbols in 1 call)
    - Aggressive caching
    - NO rate limiting needed (100k calls/month)
    """
    
    @staticmethod
    async def get_us_stock_price(symbol: str) -> Optional[Dict]:
        """Get latest price for US stock"""
        try:
            symbol = symbol.upper()
            
            # Check cache
            cached = _get_cached_us_quote(symbol)
            if cached:
                return cached
            
            # ✅ Use EODHD batch endpoint (even for 1 symbol - it's cached!)
            results = await EODHDService.get_batch_latest_eod([symbol], "US")
            
            data = results.get(symbol)
            
            if not data:
                return None
            
            # ✅ Format result
            result = {
                'symbol': symbol,
                'price': float(data.get('price', 0)),
                'current_price': float(data.get('close', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'open': float(data.get('open', 0)),
                'open_price': float(data.get('open', 0)),
                'previous_close': float(data.get('close', 0)),
                'change': 0.0,  # Calculate if needed
                'change_percent': 0.0,
                'volume': float(data.get('volume', 0)),
                'timestamp': datetime.now()
            }
            
            _set_cached_us_quote(symbol, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting US stock price for {symbol}: {e}")
            return None
    
    @staticmethod
    async def get_us_stock_candles(
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """Get historical data for US stocks"""
        try:
            symbol = symbol.upper()
            
            logger.info(f"Fetching historical data for {symbol}")
            
            # ✅ FIX: Remove retry_count parameter (doesn't exist in EODHDService)
            df = await EODHDService.get_eod_data(
                ticker=symbol,
                exchange="US",
                from_date=start_date,
                to_date=end_date,
                period="d"
            )
            
            if df is None or df.empty:
                logger.warning(f"⚠️ No data from EODHD for {symbol}")
                return None
            
            logger.info(f"✅ {symbol}: {len(df)} records")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting candles for {symbol}: {e}")
            return None
    
    @staticmethod
    async def get_multiple_us_stock_quotes(symbols: List[str]) -> Dict[str, Optional[Dict]]:
        """
        ✅ OPTIMIZED: Batch request for multiple stocks (1 API call!)
        """
        results = {}
        
        # Check cache first
        uncached_symbols = []
        for symbol in symbols:
            symbol = symbol.upper()
            cached = _get_cached_us_quote(symbol)
            if cached:
                results[symbol] = cached
            else:
                uncached_symbols.append(symbol)
        
        if not uncached_symbols:
            return results
        
        # ✅ Fetch ALL uncached symbols in ONE batch call
        logger.info(f"Batch fetching {len(uncached_symbols)} symbols")
        
        batch_results = await EODHDService.get_batch_latest_eod(uncached_symbols, "US")
        
        for symbol, data in batch_results.items():
            if data:
                result = {
                    'symbol': symbol,
                    'price': float(data.get('price', 0)),
                    'current_price': float(data.get('close', 0)),
                    'high': float(data.get('high', 0)),
                    'low': float(data.get('low', 0)),
                    'open': float(data.get('open', 0)),
                    'volume': float(data.get('volume', 0)),
                    'timestamp': datetime.now()
                }
                _set_cached_us_quote(symbol, result)
                results[symbol] = result
            else:
                results[symbol] = None
        
        return results
    
    @staticmethod
    async def get_us_stocks_with_charts(symbols: List[str], period: str = "1mo") -> Dict[str, Any]:
        """
        ✅ CRITICAL FIX: Save data to DB while generating charts
        """
        try:
            from .visualization_service import StockVisualizer
            
            end_date = datetime.now()
            period_map = {
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365
            }
            
            days = period_map.get(period, 30)
            start_date = end_date - timedelta(days=days)
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            symbol_dataframes = {}
            symbol_stats = {}
            failed_symbols = []
            
            # ✅ NEW: Import session management
            from ..database.connection import get_session
            from ..database.models import USStock
            
            # ✅ Get DB session
            db_session = next(get_session())
            
            try:
                for symbol in symbols:
                    symbol = symbol.upper()
                    
                    try:
                        logger.info(f"Processing {symbol}...")
                        
                        df = await asyncio.wait_for(
                            USStockService.get_us_stock_candles(
                                symbol,
                                start_date_str,
                                end_date_str
                            ),
                            timeout=30
                        )
                        
                        if df is None or df.empty:
                            logger.warning(f"No data for {symbol}")
                            failed_symbols.append(symbol)
                            continue
                        
                        # ✅ VALIDATE: Check timestamp
                        if not isinstance(df.index, pd.DatetimeIndex):
                            logger.warning(f"⚠️ {symbol}: Index is not DatetimeIndex")
                            failed_symbols.append(symbol)
                            continue
                        
                        if df.index[0].year < 2000:
                            logger.error(f"❌ {symbol}: Invalid timestamps")
                            failed_symbols.append(symbol)
                            continue
                        
                        # ✅ Validate columns
                        required_cols = ['open', 'high', 'low', 'close', 'volume']
                        if not all(col in df.columns for col in required_cols):
                            logger.error(f"❌ {symbol}: Missing columns")
                            failed_symbols.append(symbol)
                            continue
                        
                        if df['close'].max() <= 0:
                            logger.error(f"❌ {symbol}: Invalid prices")
                            failed_symbols.append(symbol)
                            continue
                        
                        # ✅ CRITICAL: SAVE TO DATABASE
                        saved_count = 0
                        for idx, row in df.iterrows():
                            try:
                                us_stock = USStock(
                                    symbol=symbol,
                                    open_price=float(row['open']),
                                    close_price=float(row['close']),
                                    high=float(row['high']),
                                    low=float(row['low']),
                                    volume=float(row['volume']),
                                    timestamp=idx  # idx is already datetime
                                )
                                db_session.add(us_stock)
                                saved_count += 1
                            except Exception as row_error:
                                logger.error(f"Failed to save row for {symbol}: {row_error}")
                                continue
                        
                        # ✅ Commit per symbol
                        if saved_count > 0:
                            try:
                                db_session.commit()
                                logger.info(f"✅ Saved {saved_count} records for {symbol} to DB")
                            except Exception as commit_error:
                                db_session.rollback()
                                logger.error(f"❌ Commit failed for {symbol}: {commit_error}")
                        
                        # Continue with visualization
                        symbol_dataframes[symbol] = df
                        
                        latest = df.iloc[-1]
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
                        
                        logger.info(f"✅ {symbol}: ${latest['close']:.2f} ({price_change_pct:+.2f}%)")
                        
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout for {symbol}")
                        failed_symbols.append(symbol)
                        continue
                    except Exception as e:
                        logger.error(f"Error for {symbol}: {e}")
                        failed_symbols.append(symbol)
                        continue
                
            finally:
                # ✅ Close DB session
                db_session.close()
            
            # ...existing chart generation...
            
            if not symbol_dataframes:
                return {
                    "error": "All symbols failed",
                    "message": f"Failed to fetch data for: {', '.join(symbols)}",
                    "failed_symbols": failed_symbols
                }
            
            charts = {}
            visualizer = StockVisualizer()
            
            for symbol, df in symbol_dataframes.items():
                try:
                    logger.info(f"📊 Creating charts for {symbol}...")
                    charts[f"{symbol}_candlestick"] = visualizer.create_candlestick_chart(df, symbol)
                    charts[f"{symbol}_technical"] = visualizer.create_technical_analysis_chart(df, symbol)
                except Exception as chart_error:
                    logger.error(f"Chart creation failed for {symbol}: {chart_error}")
            
            if len(symbol_dataframes) > 1:
                try:
                    charts["comparison"] = visualizer.create_multi_stock_comparison(symbol_dataframes)
                except Exception as comp_error:
                    logger.error(f"Comparison chart failed: {comp_error}")
            
            result = {
                'symbols': list(symbol_dataframes.keys()),
                'stats': symbol_stats,
                'charts': charts,
                'period': period,
                'start_date': start_date_str,
                'end_date': end_date_str
            }
            
            if failed_symbols:
                result['warning'] = f"Failed to fetch: {', '.join(failed_symbols)}"
                result['failed_symbols'] = failed_symbols
            
            return result
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}
