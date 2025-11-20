import logging
from typing import List, Dict
from datetime import datetime, timedelta
from tavily import Client
from ..config import TAVILY_API_KEY, NEWSDATA_API_KEY, NEWSAPI_KEY
import hashlib

logger = logging.getLogger(__name__)

class NewsSearchService:
    """
    ✅ CRITICAL FIX: Tavily-first strategy (most reliable!)
    """
    
    @staticmethod
    async def search_news(query: str, max_results: int = 10, days: int = 30) -> List[Dict]:
        """
        ✅ CRITICAL FIX: Handle missing dates gracefully
        """
        try:
            results = []
            vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
            is_vietnamese = any(char in query.lower() for char in vietnamese_chars)
            
            # ✅ STRATEGY 1: TAVILY FIRST (ALWAYS!)
            if TAVILY_API_KEY:
                logger.info(f"🚀 PRIMARY: Tavily search for '{query}' (max={max_results})")
                
                try:
                    client = Client(api_key=TAVILY_API_KEY)
                    
                    # ✅ CRITICAL: Use smart domain strategy
                    if is_vietnamese:
                        # Vietnamese financial sources
                        domains = [
                            "vnexpress.net",
                            "cafef.vn",
                            "vietstock.vn",
                            "ndh.vn",
                            "dantri.com.vn",
                            "baomoi.com",
                            "vietnambiz.vn",
                            "cafebiz.vn",
                            "tinnhanhchungkhoan.vn",
                            "vn.investing.com"
                        ]
                        logger.info(f"   🇻🇳 Vietnamese mode: {len(domains)} domains")
                    else:
                        # International financial sources
                        domains = [
                            "reuters.com",
                            "bloomberg.com",
                            "cnbc.com",
                            "marketwatch.com",
                            "investing.com",
                            "seekingalpha.com",
                            "finance.yahoo.com",
                            "ft.com",
                            "wsj.com",
                            "forbes.com"
                        ]
                        logger.info(f"   🌍 English mode: {len(domains)} domains")
                    
                    # ✅ CRITICAL: Request MORE than needed (filter later)
                    tavily_max = min(max_results * 3, 50)  # Request 3x, max 50
                    
                    response = client.search(
                        query,
                        max_results=tavily_max,
                        search_depth="advanced",  # ✅ Best quality
                        include_domains=domains,
                        days=days  # ✅ Filter by date
                    )
                    
                    tavily_results = response.get("results", [])
                    logger.info(f"   📦 Tavily raw: {len(tavily_results)} articles")
                    
                    # ✅ CRITICAL FIX: Use current time for missing dates
                    today = datetime.now()
                    cutoff_date = today - timedelta(days=days)
                    
                    filtered_count = 0
                    for item in tavily_results:
                        # ✅ Parse and validate date
                        pub_date_str = item.get("published_date", "")
                        
                        # ✅ FIX: If no date, use current time (assume fresh)
                        if not pub_date_str:
                            pub_date = today
                            logger.debug(f"   📅 No date provided, using today: {item.get('title', '')[:50]}")
                        else:
                            try:
                                # Try ISO format
                                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                                
                                # ✅ CRITICAL: Skip if older than cutoff
                                if pub_date.date() < cutoff_date.date():
                                    logger.debug(f"   ⏰ Skipping old article: {pub_date.date()} < {cutoff_date.date()}")
                                    filtered_count += 1
                                    continue
                                    
                            except Exception as date_error:
                                # ✅ FIX: Don't log warning, just use today
                                pub_date = today
                                logger.debug(f"   📅 Date parse failed, using today")
                        
                        # ✅ Validate content length
                        content = item.get("content", "")
                        if len(content) < 200:
                            logger.debug(f"   📏 Skipping short content: {len(content)} chars")
                            continue
                        
                        # ✅ Extract clean domain
                        url = item.get("url", "")
                        domain = item.get("domain", "")
                        
                        if not domain:
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(url)
                                domain = parsed.netloc.replace("www.", "")
                            except:
                                domain = "Unknown"
                        
                        results.append({
                            "title": item.get("title", ""),
                            "content": content,
                            "url": url,
                            "source": domain,
                            "published_date": pub_date.isoformat(),
                            "score": item.get("score", 0.8)  # Tavily provides relevance score
                        })
                    
                    logger.info(f"   ✅ Tavily filtered: {len(results)} articles (removed {filtered_count} old)")
                    
                    # ✅ If Tavily gave us enough, return immediately
                    if len(results) >= max_results:
                        logger.info(f"🎯 Tavily SUCCESS: {len(results)} articles (target={max_results})")
                        return NewsSearchService._format_results(results, max_results)
                    
                except Exception as tavily_error:
                    logger.error(f"❌ Tavily error: {tavily_error}")
            
            # ✅ STRATEGY 2: NewsData.io (ONLY if Tavily insufficient)
            if len(results) < max_results:
                shortage = max_results - len(results)
                logger.warning(f"⚠️ Tavily gave {len(results)}/{max_results}, trying NewsData.io for {shortage} more...")
                
                from ..services.newsdata_service import NewsDataService
                
                try:
                    newsdata_results = await NewsDataService.search_news(
                        query=query,
                        language="vi" if is_vietnamese else "en",
                        country=None,
                        max_results=shortage
                    )
                    
                    if newsdata_results:
                        results.extend(newsdata_results)
                        logger.info(f"   ✅ NewsData.io: +{len(newsdata_results)} articles")
                except Exception as nd_error:
                    logger.error(f"❌ NewsData.io error: {nd_error}")
            
            # ✅ STRATEGY 3: NewsAPI.org (LAST RESORT, English only)
            if len(results) < max_results and not is_vietnamese and NEWSAPI_KEY:
                shortage = max_results - len(results)
                logger.warning(f"⚠️ Still short, trying NewsAPI.org for {shortage} more...")
                
                from ..services.newsdata_service import NewsAPIService
                
                try:
                    newsapi_results = await NewsAPIService.search_news(
                        query,
                        "en",
                        shortage
                    )
                    
                    if newsapi_results:
                        results.extend(newsapi_results)
                        logger.info(f"   ✅ NewsAPI.org: +{len(newsapi_results)} articles")
                except Exception as na_error:
                    logger.error(f"❌ NewsAPI.org error: {na_error}")
            
            # ✅ Final formatting
            if results:
                logger.info(f"🎉 TOTAL: {len(results)} articles from all sources")
            else:
                logger.warning(f"⚠️ NO RESULTS from any API for: '{query}'")
            
            return NewsSearchService._format_results(results, max_results)
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    @staticmethod
    def _format_results(results: List[Dict], max_results: int) -> List[Dict]:
        """
        ✅ IMPROVED: Better deduplication + strict date sorting
        """
        seen_urls = set()
        seen_titles = set()
        unique_results = []
        
        # ✅ CRITICAL: Sort by date (newest first)
        try:
            results_sorted = sorted(
                results,
                key=lambda x: datetime.fromisoformat(x.get("published_date", "").replace("Z", "+00:00")),
                reverse=True
            )
            logger.info(f"📅 Sorted {len(results_sorted)} articles by date")
        except Exception as sort_error:
            logger.warning(f"⚠️ Date sort failed: {sort_error}, using original order")
            results_sorted = results
        
        for item in results_sorted:
            url = item.get("url", "")
            
            if not url or url in seen_urls:
                continue
            
            seen_urls.add(url)
            
            title = item.get("title", "")
            content = item.get("content", "")
            
            # ✅ Skip if content too short
            if len(content) < 100:
                continue
            
            # ✅ Check for duplicate titles (fuzzy)
            title_hash = hashlib.md5(title.lower().encode()).hexdigest()
            if title_hash in seen_titles:
                continue
            seen_titles.add(title_hash)
            
            # ✅ Create snippet
            snippet = content[:500] + "..." if len(content) > 500 else content
            
            # ✅ Create unique ID
            article_id = hashlib.md5(url.encode()).hexdigest()
            
            unique_results.append({
                "id": article_id,
                "title": title,
                "snippet": snippet,
                "full_content": content, 
                "url": url,
                "source": item.get("source", "Unknown"),
                "published_date": item.get("published_date", datetime.now().isoformat()),
                "score": item.get("score", 0.5)
            })
            
            if len(unique_results) >= max_results:
                break
        
        logger.info(f"✅ Final: {len(unique_results)} unique articles (from {len(results)} raw)")
        return unique_results
