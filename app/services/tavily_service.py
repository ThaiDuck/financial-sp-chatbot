import logging
from typing import Optional, Dict, Any
from datetime import datetime
from tavily import Client
from ..config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

class TavilySearch:
    """Tavily API wrapper for financial news search"""
    
    @staticmethod
    async def search_financial_news(query: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Search financial news using Tavily API"""
        try:
            if not TAVILY_API_KEY:
                logger.warning("Tavily API key not configured")
                return {"results": [], "error": "Tavily not configured"}
            
            client = Client(api_key=TAVILY_API_KEY)
            
            search_query = f"{query} financial news market"
            if category:
                search_query += f" {category}"
            
            response = client.search(search_query, max_results=10)
            
            return {
                "results": response.get("results", []),
                "query": query,
                "timestamp": str(__import__("datetime").datetime.now())
            }
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return {"results": [], "error": str(e)}

class DateServices:
    """Service for getting current date information"""
    
    @staticmethod
    async def get_current_date():
        """Get current date"""
        try:
            # ✅ FIXED: Don't call async function here
            current_date = datetime.now()
            
            return {
                "date": current_date.strftime("%Y-%m-%d"),
                "full_date": current_date.strftime("%A, %B %d, %Y"),
                "day": current_date.day,
                "month": current_date.month,
                "year": current_date.year,
                "day_of_week": current_date.strftime("%A"),
                "timestamp": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "system_time"
            }
        except Exception as e:
            logger.error(f"Error getting date: {e}")
            current_date = datetime.now()
            return {
                "date": current_date.strftime("%Y-%m-%d"),
                "full_date": current_date.strftime("%A, %B %d, %Y"),
                "day": current_date.day,
                "month": current_date.month,
                "year": current_date.year,
                "day_of_week": current_date.strftime("%A"),
                "timestamp": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "system_time_fallback"
            }
