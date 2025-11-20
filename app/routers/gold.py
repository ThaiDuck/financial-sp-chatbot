import logging
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from ..services.gold_service import GoldPriceService
from ..database.connection import get_session
from ..database.models import GoldPrice
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gold",
    tags=["gold"],
    responses={404: {"description": "Not found"}},
)

@router.get("/prices")
async def get_gold_prices(session: Session = Depends(get_session)):
    """
    ✅ IMPROVED: Fetch from API + save to DB for history
    """
    try:
        prices = await GoldPriceService.get_all_gold_prices()
        
        # ✅ Save VN gold to database for historical tracking
        if prices.get("vn"):
            for gold_item in prices["vn"]:
                try:
                    gold_price = GoldPrice(
                        source=gold_item.get("source", "Unknown"),
                        type=gold_item.get("type", "Unknown"),
                        location=gold_item.get("location", "Vietnam"),
                        buy_price=gold_item.get("buy_price", 0),
                        sell_price=gold_item.get("sell_price", 0),
                        timestamp=datetime.now()
                    )
                    session.add(gold_price)
                except Exception as e:
                    logger.error(f"Error saving gold price: {e}")
            
            try:
                session.commit()
                logger.info(f"✅ Saved {len(prices['vn'])} gold prices to DB")
            except Exception as e:
                session.rollback()
                logger.error(f"Error committing gold prices: {e}")
        
        return {
            "success": True,
            "data": prices
        }
    except Exception as e:
        logger.error(f"Error getting gold prices: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/prices/vn")
async def get_vn_gold_prices():
    """Get VN gold prices only"""
    try:
        prices = await GoldPriceService.get_vn_gold_prices()
        return {
            "success": True,
            "data": prices or []
        }
    except Exception as e:
        logger.error(f"Error getting VN gold prices: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/prices/international")
async def get_intl_gold_prices():
    """Get international gold prices"""
    try:
        prices = await GoldPriceService.get_international_gold_prices()
        return {
            "success": True,
            "data": prices or []
        }
    except Exception as e:
        logger.error(f"Error getting international gold prices: {e}")
        return {
            "success": False,
            "error": str(e)
        }

