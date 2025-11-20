import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)

# ✅ NEW: Apised Gold API (MUCH BETTER!)
APISED_BASE_URL = "https://gold.g.apised.com/v1"
APISED_API_KEY = "sk_BEEA66d20929D5e7F3699fD38B1654D9463271F4C1878282"

# ✅ KEEP: GoldAPI.io as backup
GOLDAPI_ENDPOINT = "https://www.goldapi.io/api/XAU/USD"
GOLDAPI_KEY = "goldapi-5p29ha19mhei71v1-io"

class GoldPriceService:
    """Service để lấy giá vàng"""
    
    @staticmethod
    async def get_vn_gold_prices() -> Optional[List[Dict]]:
        """
        ✅ IMPROVED: Better error handling + fallback
        """
        try:
            url = f"{APISED_BASE_URL}/latest"
            
            params = {
                "metals": "XAU",
                "base_currency": "VND",
                "currencies": "VND",
                "weight_unit": "gram"
            }
            
            headers = {
                "x-api-key": APISED_API_KEY
            }
            
            logger.info(f"Fetching from Apised Gold API...")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 401:
                logger.error("❌ Apised API key invalid")
                return GoldPriceService._get_fallback_vn_gold()
            
            if response.status_code == 429:
                logger.error("❌ Apised rate limit exceeded")
                return GoldPriceService._get_fallback_vn_gold()
            
            if response.status_code != 200:
                logger.error(f"❌ Apised returned {response.status_code}")
                return GoldPriceService._get_fallback_vn_gold()
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"❌ Apised error: {data}")
                return GoldPriceService._get_fallback_vn_gold()
            
            # ✅ Parse response
            metal_prices = data.get("data", {}).get("metal_prices", {}).get("XAU", {})
            
            if not metal_prices:
                logger.warning("⚠️ No metal prices in response")
                return GoldPriceService._get_fallback_vn_gold()
            
            # ✅ Extract prices
            current_price = float(metal_prices.get("price", 0))
            price_24k = float(metal_prices.get("price_24k", current_price))
            price_22k = float(metal_prices.get("price_22k", 0))
            price_18k = float(metal_prices.get("price_18k", 0))
            
            open_price = float(metal_prices.get("open", 0))
            high_price = float(metal_prices.get("high", 0))
            low_price = float(metal_prices.get("low", 0))
            prev_price = float(metal_prices.get("prev", 0))
            change = float(metal_prices.get("change", 0))
            change_pct = float(metal_prices.get("change_percentage", 0))
            
            # ✅ Create result - simulate buy/sell spread (±1%)
            buy_price_24k = price_24k * 0.99  # Buy price is 1% lower
            sell_price_24k = price_24k * 1.01  # Sell price is 1% higher
            
            gold_data = [
                {
                    "source": "Apised Gold API",
                    "type": "Vàng 24K (SJC tương đương)",
                    "buy_price": buy_price_24k,
                    "sell_price": sell_price_24k,
                    "location": "Vietnam",
                    "timestamp": datetime.now().isoformat(),
                    "currency": "VND/gram",
                    "details": {
                        "current_price": current_price,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "prev": prev_price,
                        "change": change,
                        "change_pct": change_pct
                    }
                },
                {
                    "source": "Apised Gold API",
                    "type": "Vàng 22K (9999)",
                    "buy_price": price_22k * 0.99,
                    "sell_price": price_22k * 1.01,
                    "location": "Vietnam",
                    "timestamp": datetime.now().isoformat(),
                    "currency": "VND/gram"
                },
                {
                    "source": "Apised Gold API",
                    "type": "Vàng 18K",
                    "buy_price": price_18k * 0.99,
                    "sell_price": price_18k * 1.01,
                    "location": "Vietnam",
                    "timestamp": datetime.now().isoformat(),
                    "currency": "VND/gram"
                }
            ]
            
            logger.info(f"✅ Apised Gold API: {len(gold_data)} prices")
            logger.info(f"   24K: {price_24k:,.0f} VND/gram ({change_pct:+.2f}%)")
            
            return gold_data
            
        except requests.exceptions.Timeout:
            logger.error("❌ Apised timeout")
            return GoldPriceService._get_fallback_vn_gold()
        except Exception as e:
            logger.error(f"❌ Apised error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return GoldPriceService._get_fallback_vn_gold()
    
    @staticmethod
    def _get_fallback_vn_gold() -> List[Dict]:
        """
        ✅ NEW: Fallback gold prices (static/estimated)
        Better than returning None!
        """
        logger.warning("⚠️ Using fallback gold prices")
        
        # Approximate current gold prices (update monthly)
        fallback_24k = 87_500_000  # VND per tael (37.5g) ≈ 2,333,000 VND/gram
        fallback_per_gram = fallback_24k / 37.5
        
        return [
            {
                "source": "Fallback (Estimated)",
                "type": "Vàng 24K (SJC tương đương)",
                "buy_price": fallback_per_gram * 0.99,
                "sell_price": fallback_per_gram * 1.01,
                "location": "Vietnam",
                "timestamp": datetime.now().isoformat(),
                "currency": "VND/gram",
                "details": {
                    "note": "Estimated prices - API unavailable"
                }
            }
        ]
    
    @staticmethod
    async def get_international_gold_prices() -> Optional[List[Dict]]:
        """
        ✅ KEEP: GoldAPI.io for international prices
        """
        try:
            headers = {
                "x-access-token": GOLDAPI_KEY,
                "Content-Type": "application/json"
            }
            
            response = requests.get(GOLDAPI_ENDPOINT, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return [{
                    "source": "GoldAPI.io",
                    "type": "Gold Spot Price",
                    "price_usd": float(data.get("price", 0)),
                    "high_24h": float(data.get("high_price_24h", 0)),
                    "low_24h": float(data.get("low_price_24h", 0)),
                    "open": float(data.get("open_price", 0)),
                    "timestamp": datetime.now().isoformat(),
                    "currency": "USD/oz"
                }]
            
            logger.warning(f"GoldAPI returned {response.status_code}")
            return []  # ✅ Return empty list instead of None
            
        except Exception as e:
            logger.error(f"Error getting international gold: {e}")
            return []  # ✅ Return empty list
    
    @staticmethod
    async def get_all_gold_prices() -> Dict:
        """Get all gold prices"""
        try:
            vn_prices, intl_prices = await asyncio.gather(
                GoldPriceService.get_vn_gold_prices(),
                GoldPriceService.get_international_gold_prices(),
                return_exceptions=True
            )
            
            if isinstance(vn_prices, Exception):
                logger.error(f"VN gold error: {vn_prices}")
                vn_prices = GoldPriceService._get_fallback_vn_gold()  # ✅ Use fallback
            
            if isinstance(intl_prices, Exception):
                logger.error(f"Intl gold error: {intl_prices}")
                intl_prices = []
            
            return {
                "vn": vn_prices or [],
                "international": intl_prices or [],
                "timestamp": datetime.now().isoformat(),
                "sources": {
                    "vn": "Apised Gold API → Fallback",
                    "international": "GoldAPI.io"
                }
            }
        except Exception as e:
            logger.error(f"Error in get_all_gold_prices: {e}")
            return {
                "vn": GoldPriceService._get_fallback_vn_gold(),
                "international": [],
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }