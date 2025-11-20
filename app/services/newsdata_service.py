import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ..config import NEWSDATA_API_KEY, NEWSAPI_KEY
import urllib.parse

logger = logging.getLogger(__name__)

class NewsDataService:
    """
    NewsData.io API wrapper
    Free tier: 200 credits/day (10 articles per credit = 2000 articles/day max)
    """
    
    ARCHIVE_URL = "https://newsdata.io/api/1/archive"
    LATEST_URL = "https://newsdata.io/api/1/latest"  # ✅ NEW: Use latest for better results
    
    @staticmethod
    async def search_news(
        query: str,
        language: str = "en",
        country: Optional[str] = None,
        category: str = "business",
        max_results: int = 10,
        days_back: int = 7
    ) -> List[Dict]:
        """
        ✅ IMPROVED: Try BOTH latest AND archive endpoints
        """
        try:
            if not NEWSDATA_API_KEY:
                logger.warning("NewsData.io API key not configured")
                return []
            
            all_results = []
            
            # ✅ STRATEGY 1: Try "latest" endpoint first (more results)
            logger.info(f"Trying NewsData.io LATEST endpoint for '{query}' (lang={language})")
            
            params_latest = {
                "apikey": NEWSDATA_API_KEY,
                "q": query,
                "language": language,
            }
            
            if country:
                params_latest["country"] = country
            if category:
                params_latest["category"] = category
            
            try:
                response = requests.get(NewsDataService.LATEST_URL, params=params_latest, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("status") == "success":
                        results = data.get("results", [])
                        logger.info(f"✅ Latest endpoint: {len(results)} articles")
                        
                        for item in results[:max_results]:
                            content = item.get("content") or item.get("description") or ""
                            if len(content) < 100:
                                continue
                            
                            all_results.append({
                                "title": item.get("title", ""),
                                "content": content,
                                "url": item.get("link", ""),
                                "source": item.get("source_id", "Unknown"),
                                "published_date": item.get("pubDate", datetime.now().isoformat()),
                            })
                else:
                    logger.warning(f"Latest endpoint failed: {response.status_code}")
            except Exception as latest_error:
                logger.error(f"Latest endpoint error: {latest_error}")
            
            # ✅ STRATEGY 2: Also try "archive" endpoint
            if len(all_results) < max_results:
                logger.info(f"Trying NewsData.io ARCHIVE endpoint")
                
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)
                
                params_archive = {
                    "apikey": NEWSDATA_API_KEY,
                    "q": query,
                    "language": language,
                    "from_date": start_date.strftime("%Y-%m-%d"),
                    "to_date": end_date.strftime("%Y-%m-%d")
                }
                
                if country:
                    params_archive["country"] = country
                
                try:
                    response = requests.get(NewsDataService.ARCHIVE_URL, params=params_archive, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get("status") == "success":
                            results = data.get("results", [])
                            logger.info(f"✅ Archive endpoint: {len(results)} articles")
                            
                            for item in results[:max_results]:
                                content = item.get("content") or item.get("description") or ""
                                if len(content) < 100:
                                    continue
                                
                                all_results.append({
                                    "title": item.get("title", ""),
                                    "content": content,
                                    "url": item.get("link", ""),
                                    "source": item.get("source_id", "Unknown"),
                                    "published_date": item.get("pubDate", datetime.now().isoformat()),
                                })
                except Exception as archive_error:
                    logger.error(f"Archive endpoint error: {archive_error}")
            
            logger.info(f"✅ NewsData.io total: {len(all_results)} articles for '{query}'")
            return all_results[:max_results]
            
        except Exception as e:
            logger.error(f"NewsData.io error: {e}")
            return []
    
    @staticmethod
    async def search_vietnam_news(query: str, max_results: int = 10) -> List[Dict]:
        """Search Vietnamese news"""
        return await NewsDataService.search_news(
            query=query,
            language="vi",
            country=None,  # ✅ FIX: Don't specify country if getting 403
            category="business",
            max_results=max_results,
            days_back=30
        )
    
    @staticmethod
    async def search_us_news(query: str, max_results: int = 10) -> List[Dict]:
        """Search US news"""
        return await NewsDataService.search_news(
            query=query,
            language="en",
            country="us",
            category="business",
            max_results=max_results,
            days_back=30
        )

class NewsAPIService:
    """
    ✅ FIXED: Use official newsapi-python library with correct field parsing
    Free tier: 100 requests/day
    """
    
    @staticmethod
    async def search_news(query: str, language: str = "en", max_results: int = 10) -> List[Dict]:
        """
        Search using NewsAPI.org official library
        ✅ FIXED: Handle truncated content properly
        """
        try:
            if not NEWSAPI_KEY:
                logger.warning("NewsAPI key not configured")
                return []
            
            from newsapi import NewsApiClient
            
            newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
            
            # Calculate date range (last 30 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # ✅ FIX: Map Vietnamese to English for NewsAPI
            # NewsAPI doesn't support 'vi', only major languages
            api_language = "en" if language == "vi" else language
            
            # ✅ Add Vietnamese sources manually if searching in Vietnamese
            sources = None
            if language == "vi":
                # Focus on international sources covering Vietnam
                # NewsAPI doesn't have Vietnamese sources
                logger.info("Searching English sources for Vietnamese market news")
            
            # Use get_everything() for keyword search
            response = newsapi.get_everything(
                q=query,
                language=api_language,
                sources=sources,
                from_param=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d'),
                sort_by='publishedAt',
                page_size=min(max_results, 100)
            )
            
            if response.get('status') != 'ok':
                logger.error(f"NewsAPI error: {response.get('message')}")
                return []
            
            results = []
            for item in response.get('articles', [])[:max_results]:
                # ✅ FIXED: Extract source correctly (it's an object)
                source_obj = item.get('source', {})
                source_name = source_obj.get('name', 'Unknown') if isinstance(source_obj, dict) else str(source_obj)
                
                # ✅ Get description and content
                description = item.get('description', '') or ''
                content = item.get('content', '') or ''
                
                # ✅ FIXED: Remove "[+X chars]" truncation marker from content
                if content and '[+' in content and 'chars]' in content:
                    # Remove the truncation marker
                    content = content.split('[+')[0].strip()
                
                # ✅ Combine description and content intelligently
                # If content is truncated, description might have more info
                if description and content:
                    # Check if content is just description repeated
                    if content.startswith(description[:50]):
                        full_content = content  # Content includes description
                    else:
                        full_content = f"{description}\n\n{content}"  # Separate
                else:
                    full_content = description or content or ""
                
                # ✅ Clean and validate
                full_content = full_content.strip()
                
                # Skip if too short (probably truncated badly)
                if len(full_content) < 100:
                    logger.debug(f"Skipping short content: {item.get('title', '')[:50]}")
                    continue
                
                # ✅ Extract author properly
                author = item.get('author', '')
                if author and isinstance(author, str):
                    # Clean up author field (remove repetition like "John Doe, Contributor, \n John Doe")
                    author = author.split(',')[0].strip()
                
                results.append({
                    "title": item.get('title', ''),
                    "content": full_content,
                    "url": item.get('url', ''),
                    "source": source_name,
                    "published_date": item.get('publishedAt', datetime.now().isoformat()),
                    "image_url": item.get('urlToImage'),
                    "language": language,
                    "author": author
                })
            
            logger.info(f"✅ NewsAPI.org: {len(results)} articles for '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"NewsAPI.org error: {e}")
            return []
    
    @staticmethod
    async def get_top_headlines(
        category: str = 'business',
        country: str = 'us',
        max_results: int = 10
    ) -> List[Dict]:
        """
        Get top headlines (for proactive crawling)
        ✅ FIXED: Same parsing improvements
        """
        try:
            if not NEWSAPI_KEY:
                return []
            
            from newsapi import NewsApiClient
            
            newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
            
            response = newsapi.get_top_headlines(
                category=category,
                country=country,
                page_size=min(max_results, 100)
            )
            
            if response.get('status') != 'ok':
                return []
            
            results = []
            for item in response.get('articles', [])[:max_results]:
                # ✅ Same parsing logic
                source_obj = item.get('source', {})
                source_name = source_obj.get('name', 'Unknown') if isinstance(source_obj, dict) else str(source_obj)
                
                description = item.get('description', '') or ''
                content = item.get('content', '') or ''
                
                # Remove truncation marker
                if content and '[+' in content:
                    content = content.split('[+')[0].strip()
                
                # Combine intelligently
                if description and content:
                    if content.startswith(description[:50]):
                        full_content = content
                    else:
                        full_content = f"{description}\n\n{content}"
                else:
                    full_content = description or content or ""
                
                full_content = full_content.strip()
                
                if len(full_content) < 100:
                    continue
                
                author = item.get('author', '')
                if author and isinstance(author, str):
                    author = author.split(',')[0].strip()
                
                results.append({
                    "title": item.get('title', ''),
                    "content": full_content,
                    "url": item.get('url', ''),
                    "source": source_name,
                    "published_date": item.get('publishedAt', datetime.now().isoformat()),
                    "image_url": item.get('urlToImage'),
                    "language": 'en',
                    "author": author
                })
            
            logger.info(f"✅ NewsAPI top headlines: {len(results)} articles")
            return results
            
        except Exception as e:
            logger.error(f"NewsAPI top headlines error: {e}")
            return []
