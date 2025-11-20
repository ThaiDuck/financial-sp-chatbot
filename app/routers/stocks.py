import logging
from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import Depends
from ..database.connection import get_session
from ..services.stock_service import get_latest_stock_price
from ..services.stock_us_service import USStockService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/stocks",
    tags=["stocks"],
    responses={404: {"description": "Not found"}},
)

@router.post("/vn/update")
async def update_vn_stocks(symbols: list[str], session: Session = Depends(get_session)):
    """Update VN stock data for given symbols"""
    try:
        from ..services.stock_service import fetch_vn_stock_data, save_vn_stock_data
        
        stock_data = await fetch_vn_stock_data(symbols)
        saved = await save_vn_stock_data(session, stock_data)
        
        return {
            "success": saved,
            "symbols": symbols,
            "records": len(stock_data)
        }
    except Exception as e:
        logger.error(f"Error updating VN stocks: {e}")
        return {"success": False, "error": str(e)}

@router.post("/us/update")
async def update_us_stocks(symbols: list[str], session: Session = Depends(get_session)):
    """
    ✅ FIXED: Update US stock data AND save to database
    """
    try:
        from ..services.stock_us_service import USStockService
        from ..database.models import USStock
        from datetime import datetime
        
        results = []
        saved_count = 0
        
        for symbol in symbols:
            try:
                logger.info(f"Fetching {symbol}...")
                
                # Get price data
                price = await USStockService.get_us_stock_price(symbol)
                
                if price:
                    results.append(price)
                    
                    # ✅ CRITICAL: Save to database
                    us_stock = USStock(
                        symbol=symbol,
                        open_price=price.get('open', 0),
                        close_price=price.get('current_price', 0),
                        high=price.get('high', 0),
                        low=price.get('low', 0),
                        volume=price.get('volume', 0),
                        timestamp=datetime.now()
                    )
                    
                    session.add(us_stock)
                    saved_count += 1
                    logger.info(f"✅ {symbol}: ${price.get('current_price', 0):.2f}")
                else:
                    logger.warning(f"⚠️ No data for {symbol}")
                    
            except Exception as e:
                logger.error(f"❌ Error for {symbol}: {e}")
                continue
        
        # ✅ Commit all at once
        if saved_count > 0:
            try:
                session.commit()
                logger.info(f"✅ Saved {saved_count} US stocks to DB")
            except Exception as e:
                session.rollback()
                logger.error(f"❌ Failed to save: {e}")
        
        return {
            "success": True,
            "symbols": symbols,
            "records": len(results),
            "saved_to_db": saved_count,
            "data": results
        }
    except Exception as e:
        logger.error(f"Error updating US stocks: {e}")
        session.rollback()
        return {"success": False, "error": str(e)}

@router.get("/vn/charts")
async def get_vn_stocks_charts(
    symbols: str = Query(..., description="Comma-separated stock symbols (e.g., VCB,VHM,FPT)"),
    period: str = Query("1mo", description="Time period: 1d, 1w, 1mo, 3mo, 6mo, 1y"),
    session: Session = Depends(get_session)
):
    try:
        from ..services.stock_service import get_vn_stocks_with_charts
        
        # Validate period
        valid_periods = ["1d", "1w", "1mo", "3mo", "6mo", "1y"]
        if period.lower() not in valid_periods:
            return {
                "success": False,
                "error": f"Invalid period. Must be one of: {', '.join(valid_periods)}"
            }
        
        # Parse symbols
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        
        if not symbol_list:
            return {
                "success": False,
                "error": "No valid symbols provided"
            }
        
        logger.info(f"📊 Fetching charts for VN symbols: {symbol_list} (period={period})")
        
        result = await get_vn_stocks_with_charts(session, symbol_list, period)
        
        # Check for errors
        if "error" in result:
            return {
                "success": False,
                "error": result.get("error"),
                "message": result.get("message", "No data available")
            }
        
        # Validate symbols exist
        if "symbols" not in result or not result["symbols"]:
            return {
                "success": False,
                "error": "No valid data found",
                "message": "No data available for the requested symbols"
            }
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error getting VN stocks with charts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/vn/batch")
async def get_vn_stocks_batch(
    symbols: str = Query(..., description="Comma-separated stock symbols"),
    session: Session = Depends(get_session)
):
    """Get real-time quotes for multiple VN stocks"""
    try:
        from ..services.stock_service import get_multiple_vn_stock_quotes
        
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        results = await get_multiple_vn_stock_quotes(symbol_list)
        
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"Error getting batch VN stocks: {e}")
        return {"success": False, "error": str(e)}

@router.get("/us/charts")
async def get_us_stocks_charts(
    symbols: str = Query(..., description="Comma-separated stock symbols (e.g., AAPL,MSFT,GOOGL)"),
    period: str = Query("1mo", description="Time period: 1mo, 3mo, 6mo, 1y")
):
    try:
        from ..services.stock_us_service import USStockService
        
        # Parse symbols
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        
        if not symbol_list:
            return {
                "success": False,
                "error": "No valid symbols provided"
            }
        
        logger.info(f"Fetching charts for US symbols: {symbol_list}")
        
        result = await USStockService.get_us_stocks_with_charts(symbol_list, period)
        
        # Check for error
        if "error" in result:
            return {
                "success": False,
                "error": result.get("error"),
                "message": result.get("message", "No data available")
            }
        
        # Validate symbols
        if "symbols" not in result or not result["symbols"]:
            return {
                "success": False,
                "error": "No valid data found",
                "message": "No data available for the requested symbols"
            }
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error getting US stocks with charts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/us/batch")
async def get_us_stocks_batch(
    symbols: str = Query(..., description="Comma-separated stock symbols")
):
    """Get real-time quotes for multiple US stocks"""
    try:
        from ..services.stock_us_service import USStockService
        
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        results = await USStockService.get_multiple_us_stock_quotes(symbol_list)
        
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"Error getting batch US stocks: {e}")
        return {"success": False, "error": str(e)}

@router.get("/vn/{symbol}")
async def get_vn_stock(symbol: str, session: Session = Depends(get_session)):
    """
    Get Vietnamese stock price
    ✅ This route is registered LAST to avoid catching /vn/charts or /vn/batch
    """
    try:
        price = await get_latest_stock_price(session, symbol, is_vn_stock=True)
        if not price:
            return {"success": False, "error": f"No data for {symbol}"}
        return {"success": True, "data": price}
    except Exception as e:
        logger.error(f"Error getting VN stock: {e}")
        return {"success": False, "error": str(e)}

@router.get("/us/{symbol}")
async def get_us_stock(symbol: str):
    """Get US stock price"""
    try:
        price = await USStockService.get_us_stock_price(symbol)
        if not price:
            return {"success": False, "error": f"No data for {symbol}"}
        return {"success": True, "data": price}
    except Exception as e:
        logger.error(f"Error getting US stock: {e}")
        return {"success": False, "error": str(e)}
