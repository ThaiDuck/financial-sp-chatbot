from langchain.tools import Tool, StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Optional, List
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
from ..services.gold_service import GoldPriceService
from ..services.stock_service import get_latest_stock_price
from ..services.stock_us_service import USStockService
from ..services.tavily_service import TavilySearch
from ..database.models import VNStock, USStock
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)

# Input schemas for tools
class StockPriceInput(BaseModel):
    symbol: str = Field(..., description="The stock symbol to look up")
    is_vn_stock: bool = Field(True, description="Whether this is a Vietnamese stock (True) or US stock (False)")

class NewsSearchInput(BaseModel):
    query: str = Field(..., description="The search query for financial news")
    category: Optional[str] = Field(None, description="Optional category filter (e.g., gold, stock)")

class DateInfo(BaseModel):
    format: Optional[str] = Field(None, description="Optional date format (e.g., 'yyyy-mm-dd', 'full')")

def create_db_tools(session: Session):
    """Create database query tools for LangChain"""
    
    def gold_prices_wrapper():
        """
        ✅ FIXED: Synchronous function (uses asyncio internally)
        """
        try:
            from ..database.models import GoldPrice
            from datetime import datetime, timedelta
            
            # ✅ Try DB first (last 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            db_prices = session.query(GoldPrice)\
                .filter(GoldPrice.timestamp >= cutoff)\
                .order_by(GoldPrice.timestamp.desc())\
                .limit(10)\
                .all()
            
            if db_prices:
                logger.info(f"✅ Gold: Using {len(db_prices)} DB records")
                
                result = []
                for price in db_prices:
                    result.append({
                        "source": price.source,
                        "type": price.type,
                        "location": price.location,
                        "buy_price": price.buy_price,
                        "sell_price": price.sell_price,
                        "timestamp": price.timestamp.isoformat()
                    })
                return result
            
            # ✅ Fallback to API if no DB data
            logger.warning("⚠️ No gold data in DB, fetching from API...")
            
            # ✅ FIX: Run async function in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            prices = loop.run_until_complete(GoldPriceService.get_all_gold_prices())
            
            # ✅ Return VN gold prices
            vn_prices = prices.get("vn", [])
            
            if vn_prices:
                logger.info(f"✅ Gold API: {len(vn_prices)} prices")
                return vn_prices
            else:
                logger.warning("⚠️ No gold prices from API")
                return []
            
        except Exception as e:
            logger.error(f"Error in gold price tool: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []  # ✅ Return empty list instead of dict with error
    
    gold_tool = Tool(
        name="gold_prices",
        description="Get the latest gold prices in Vietnam from database or live API",
        func=gold_prices_wrapper,
    )
    
    def get_stock_price_wrapper(symbol: str, is_vn_stock: bool = True):
        """
        ✅ FIXED: Format VN stock prices correctly (multiply by 1,000)
        """
        try:
            symbol = symbol.upper()
            cutoff = datetime.now() - timedelta(days=7)
            
            if is_vn_stock:
                records = session.query(VNStock)\
                    .filter(VNStock.symbol == symbol)\
                    .filter(VNStock.timestamp >= cutoff)\
                    .order_by(VNStock.timestamp.desc())\
                    .limit(10)\
                    .all()
            else:
                records = session.query(USStock)\
                    .filter(USStock.symbol == symbol)\
                    .filter(USStock.timestamp >= cutoff)\
                    .order_by(USStock.timestamp.desc())\
                    .limit(10)\
                    .all()
            
            if records:
                logger.info(f"✅ Stock {symbol}: Using {len(records)} DB records")
                
                latest = records[0]
                oldest = records[-1]
                
                # ✅ CRITICAL FIX: VN stocks need x1,000 conversion
                if is_vn_stock:
                    price_multiplier = 1000
                    currency = "VND"
                else:
                    price_multiplier = 1
                    currency = "USD"
                
                # Calculate 7-day change
                change = ((latest.close_price - oldest.close_price) / oldest.close_price) * 100
                
                return {
                    "symbol": symbol,
                    "latest_price": latest.close_price * price_multiplier,
                    "open": latest.open_price * price_multiplier,
                    "high": latest.high * price_multiplier,
                    "low": latest.low * price_multiplier,
                    "volume": latest.volume,
                    "currency": currency,
                    "timestamp": latest.timestamp.isoformat(),
                    "period_analysis": {
                        "7day_change": change,
                        "7day_high": max(r.high for r in records) * price_multiplier,
                        "7day_low": min(r.low for r in records) * price_multiplier,
                        "avg_volume": sum(r.volume for r in records) / len(records),
                        "data_points": len(records)
                    }
                }
            
            # ✅ Fallback to API
            logger.warning(f"⚠️ No DB data for {symbol}, fetching from API...")
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            price = loop.run_until_complete(get_latest_stock_price(session, symbol, is_vn_stock))
            if not price:
                return {"error": f"No data found for stock symbol {symbol}"}
            return price
            
        except Exception as e:
            logger.error(f"Error in stock price tool: {e}")
            return {"error": f"Failed to retrieve stock price for {symbol}"}
    
    stock_tool = StructuredTool.from_function(
        func=get_stock_price_wrapper,
        name="stock_price",
        description="Get the latest price and 7-day analysis for a specific stock by symbol (VN or US)",
        args_schema=StockPriceInput,
    )
    
    def search_financial_news_wrapper(query: str, category: Optional[str] = None):
        """Search for financial news using Tavily."""
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            results = loop.run_until_complete(TavilySearch.search_financial_news(query, category))
            return results
        except Exception as e:
            logger.error(f"Error in news search tool: {e}")
            return {"error": "Failed to search for financial news"}
    
    news_tool = StructuredTool.from_function(
        func=search_financial_news_wrapper,
        name="search_financial_news",
        description="Search for financial news using Tavily API",
        args_schema=NewsSearchInput,
    )
    
    def get_current_date_wrapper(format: Optional[str] = None):
        """Get the current date and time."""
        try:
            now = datetime.now()
            
            if format:
                if format == "full":
                    return now.strftime("%A, %B %d, %Y at %H:%M:%S")
                elif format == "date-only":
                    return now.strftime("%Y-%m-%d")
                elif format == "time-only":
                    return now.strftime("%H:%M:%S")
                else:
                    return now.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return now.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error in date tool: {e}")
            return datetime.now().strftime("%Y-%m-%d")
    
    date_tool = StructuredTool.from_function(
        func=get_current_date_wrapper,
        name="current_date",
        description="Get the current date and time, useful for providing time-sensitive information",
        args_schema=DateInfo,
    )
    
    def get_recent_vn_stock_data(symbol: str, days: int = 7):
        """Get recent VN stock data from database"""
        try:
            symbol = symbol.upper()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            records = session.query(VNStock)\
                .filter(VNStock.symbol == symbol)\
                .filter(VNStock.timestamp >= cutoff_date)\
                .order_by(VNStock.timestamp.desc())\
                .limit(100)\
                .all()
            
            if not records:
                return {"error": f"No data found for {symbol} in last {days} days"}
            
            data = []
            for r in records:
                data.append({
                    "date": r.timestamp.strftime('%Y-%m-%d'),
                    "open": r.open_price,
                    "close": r.close_price,
                    "high": r.high,
                    "low": r.low,
                    "volume": r.volume
                })
            
            return {
                "symbol": symbol,
                "period": f"Last {days} days",
                "records": data,
                "count": len(data)
            }
        except Exception as e:
            logger.error(f"Error getting VN stock data: {e}")
            return {"error": str(e)}
    
    vn_stock_history_tool = Tool(
        name="vn_stock_recent_history",
        description="Get recent price history for Vietnamese stocks (VCB, VHM, etc.) from database. Use this for questions about recent stock performance.",
        func=lambda symbol: get_recent_vn_stock_data(symbol, 7)
    )
    
    def get_recent_us_stock_data(symbol: str, days: int = 7):
        """Get recent US stock data from database"""
        try:
            symbol = symbol.upper()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            records = session.query(USStock)\
                .filter(USStock.symbol == symbol)\
                .filter(USStock.timestamp >= cutoff_date)\
                .order_by(USStock.timestamp.desc())\
                .limit(100)\
                .all()
            
            if not records:
                return {"error": f"No data found for {symbol} in last {days} days"}
            
            data = []
            for r in records:
                data.append({
                    "date": r.timestamp.strftime('%Y-%m-%d'),
                    "open": r.open_price,
                    "close": r.close_price,
                    "high": r.high,
                    "low": r.low,
                    "volume": r.volume
                })
            
            return {
                "symbol": symbol,
                "period": f"Last {days} days",
                "records": data,
                "count": len(data)
            }
        except Exception as e:
            logger.error(f"Error getting US stock data: {e}")
            return {"error": str(e)}
    
    us_stock_history_tool = Tool(
        name="us_stock_recent_history",
        description="Get recent price history for US stocks (AAPL, MSFT, etc.) from database. Use this for questions about recent stock performance.",
        func=lambda symbol: get_recent_us_stock_data(symbol, 7)
    )
    
    def compare_stocks_wrapper(symbols: str):
        """
        ✅ FIXED: Format VN stock prices correctly in comparison
        """
        try:
            symbol_list = [s.strip().upper() for s in symbols.split(',')]
            cutoff = datetime.now() - timedelta(days=7)
            
            results = []
            
            for symbol in symbol_list:
                # Try VN first
                records = session.query(VNStock)\
                    .filter(VNStock.symbol == symbol)\
                    .filter(VNStock.timestamp >= cutoff)\
                    .order_by(VNStock.timestamp.desc())\
                    .limit(10)\
                    .all()
                
                is_vn = bool(records)
                
                if not records:
                    # Try US
                    records = session.query(USStock)\
                        .filter(USStock.symbol == symbol)\
                        .filter(USStock.timestamp >= cutoff)\
                        .order_by(USStock.timestamp.desc())\
                        .limit(10)\
                        .all()
                
                if records:
                    latest = records[0]
                    oldest = records[-1]
                    change = ((latest.close_price - oldest.close_price) / oldest.close_price) * 100
                    
                    # ✅ CRITICAL FIX: Apply correct multiplier
                    price_multiplier = 1000 if is_vn else 1
                    currency = "VND" if is_vn else "USD"
                    
                    results.append({
                        "symbol": symbol,
                        "latest_price": latest.close_price * price_multiplier,
                        "currency": currency,
                        "7day_change": change,
                        "7day_high": max(r.high for r in records) * price_multiplier,
                        "7day_low": min(r.low for r in records) * price_multiplier
                    })
            
            if results:
                # Sort by performance
                results.sort(key=lambda x: x['7day_change'], reverse=True)
                return results
            else:
                return {"error": "No data found for any of the symbols"}
                
        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            return {"error": str(e)}
    
    compare_stocks_tool = Tool(
        name="compare_stocks",
        description="Compare multiple stocks by their 7-day performance. Input: comma-separated symbols (e.g., 'VCB,VHM,FPT' or 'AAPL,MSFT,GOOGL')",
        func=compare_stocks_wrapper
    )
    
    def gold_history_wrapper(days: int = 7):
        """Get gold price history from DB"""
        try:
            from ..database.models import GoldPrice
            
            cutoff = datetime.now() - timedelta(days=days)
            
            records = session.query(GoldPrice)\
                .filter(GoldPrice.timestamp >= cutoff)\
                .filter(GoldPrice.type.like('%24K%'))\
                .order_by(GoldPrice.timestamp.desc())\
                .limit(20)\
                .all()
            
            if records:
                data = []
                for r in records:
                    data.append({
                        "date": r.timestamp.strftime('%Y-%m-%d'),
                        "source": r.source,
                        "buy_price": r.buy_price,
                        "sell_price": r.sell_price
                    })
                
                # Calculate trend
                if len(records) >= 2:
                    latest = records[0].sell_price
                    oldest = records[-1].sell_price
                    change = ((latest - oldest) / oldest) * 100
                    
                    return {
                        "period": f"Last {days} days",
                        "data_points": len(records),
                        "latest_price": latest,
                        f"{days}day_change": change,
                        "prices": data
                    }
                
                return {"prices": data}
            else:
                return {"error": f"No gold price history in DB for last {days} days"}
                
        except Exception as e:
            logger.error(f"Error getting gold history: {e}")
            return {"error": str(e)}
    
    gold_history_tool = Tool(
        name="gold_price_history",
        description="Get gold price history and trends from database (default: last 7 days)",
        func=lambda: gold_history_wrapper(7)
    )
    
    return [
        gold_tool, 
        stock_tool, 
        news_tool, 
        date_tool,
        vn_stock_history_tool,
        us_stock_history_tool,
        compare_stocks_tool,
        gold_history_tool
    ]
