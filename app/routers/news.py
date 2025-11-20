from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
import logging
from urllib.parse import urlparse
from datetime import datetime
import json
from pydantic import BaseModel
from ..database.connection import get_session
from ..services.news_search_service import NewsSearchService
from ..database.models import NewsArticle
from ..rag.embeddings import create_embedding
from ..utils.news_filter import is_valid_article_url, is_homepage_link, canonical_url, hash_title, extract_category
from ..utils.news_summarizer import summarize_article, summarize_article_direct

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/news",
    tags=["news"],
    responses={404: {"description": "Not found"}},
)

PAYWALL_DOMAINS = [
    'bloomberg.com',
    'reuters.com', 
    'wsj.com',
    'barrons.com',
    'ft.com',
    'economist.com'
]

def extract_source_name(url: str) -> str:
    """Extract readable source name from URL"""
    try:
        domain = urlparse(url).netloc.replace('www.', '')
        
        domain_map = {
            'vnexpress.net': 'VNExpress',
            'vietstock.vn': 'Vietstock',
            'cafef.vn': 'CafeF',
            'reuters.com': 'Reuters',
            'cnbc.com': 'CNBC',
            'marketwatch.com': 'MarketWatch',
            'bloomberg.com': 'Bloomberg',
            'investing.com': 'Investing.com',
            'finance.yahoo.com': 'Yahoo Finance'
        }
        
        for key, value in domain_map.items():
            if key in domain:
                return value
        
        return domain.split('.')[0].capitalize()
    except:
        return "Unknown"

def is_paywall_url(url: str) -> bool:
    """Check if URL is from a known paywall site"""
    try:
        domain = urlparse(url).netloc.lower()
        return any(paywall in domain for paywall in PAYWALL_DOMAINS)
    except:
        return False

class SummarizeRequest(BaseModel):
    url: str  # ✅ KEEP: For reference only
    title: str
    content: str  # ✅ CRITICAL: Must provide content (from search results)

class EmbedRequest(BaseModel):
    url: str
    title: str
    content: str
    source: str
    category: str = "general"

@router.get("/search")
async def search_news_on_demand(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(10, description="Max results to return"),
    days: int = Query(30, description="Search within last N days")
):
    """
    ✅ FIXED: Search ONLY - NO auto-embedding
    
    Search for financial news using APIs. 
    User can manually embed articles via UI button if needed.
    """
    try:
        logger.info(f"🔍 News search: '{query}' (max={max_results}, days={days})")
        
        results = await NewsSearchService.search_news(query, max_results, days)
        
        if not results or len(results) == 0:
            logger.warning(f"⚠️ No results from any news source for: '{query}'")
            return {
                "success": True,
                "query": query,
                "count": 0,
                "results": [],
                "message": "No articles found. Try different keywords or check API keys.",
                "stats": {
                    "total": 0,
                    "filtered": 0,
                    "duplicates": 0
                }
            }
        
        logger.info(f"📰 Got {len(results)} raw results")
        
        # Filter and deduplicate
        filtered_results = []
        seen_urls = set()
        seen_titles = set()
        
        for article in results:
            url = article.get('url', '')
            title = article.get('title', '')
            
            canonical = canonical_url(url)
            
            if canonical in seen_urls:
                logger.debug(f"⛔ Duplicate URL: {url}")
                continue
            
            title_hash = hash_title(title)
            
            if title_hash in seen_titles:
                logger.debug(f"⛔ Duplicate title: {title[:50]}")
                continue
            
            if article.get('source') == 'Unknown' or not article.get('source'):
                article['source'] = extract_source_name(url)
            
            if is_homepage_link(canonical):
                logger.debug(f"⛔ Homepage: {url}")
                continue
            
            if not is_valid_article_url(canonical, title):
                logger.debug(f"⛔ Invalid: {url}")
                continue
            
            snippet = article.get('snippet', '')
            
            if len(snippet) < 100:
                continue
            
            garbage = ['sign in', 'log in', 'subscribe now', 'menu', 'navigation']
            if any(g in snippet.lower() for g in garbage):
                continue
            
            category = extract_category(canonical, title)
            
            article['url'] = canonical
            article['canonical_url'] = canonical
            article['title_hash'] = title_hash
            article['category'] = category
            
            filtered_results.append(article)
            seen_urls.add(canonical)
            seen_titles.add(title_hash)
        
        logger.info(f"✅ Filtered: {len(results)} → {len(filtered_results)} valid (deduped)")
        
        return {
            "success": True,
            "query": query,
            "count": len(filtered_results),
            "results": filtered_results,
            "stats": {
                "total": len(results),
                "filtered": len(filtered_results),
                "duplicates": len(results) - len(filtered_results)
            }
        }
        
    except Exception as e:
        logger.error(f"Error searching news: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}

@router.post("/article/summarize")
async def summarize_article_endpoint(request: SummarizeRequest):
    """
    ✅ FIXED: Use provided content, don't fetch from URL
    """
    try:
        if len(request.content) < 200:
            return {
                "success": False,
                "error": "Content too short to summarize"
            }
        
        logger.info(f"📄 Summarizing existing content: {request.title[:50]}")
        
        summary = await summarize_article_direct(
            title=request.title,
            content=request.content,
            max_words=500
        )
        
        if not summary:
            return {
                "success": False,
                "error": "Failed to generate summary"
            }
        
        return {
            "success": True,
            "summary": summary,
            "word_count": len(summary.split())
        }
        
    except Exception as e:
        logger.error(f"Error summarizing: {e}")
        return {"success": False, "error": str(e)}

@router.post("/article/embed")
async def embed_article_endpoint(
    request: EmbedRequest,
    session: Session = Depends(get_session)
):
    """
    ✅ MANUAL ONLY: Embed article when user explicitly clicks button
    """ 
    try:
        canonical = canonical_url(request.url)
        # Check if already exists
        existing = session.query(NewsArticle).filter(NewsArticle.url == canonical).first()
        if existing:
            return {
                "success": True,
                "message": "Article already in knowledge base",
                "article_id": existing.id
            }
        
        # Validate
        if is_homepage_link(canonical):
            return {
                "success": False,
                "error": "Homepage links are not allowed"
            }
        
        if not is_valid_article_url(canonical, request.title):
            return {
                "success": False,
                "error": "Invalid article URL"
            }
        
        if len(request.content) < 200:
            return {
                "success": False,
                "error": "Content too short (minimum 200 characters)"
            }
        
        # Process and embed
        logger.info(f"📌 Manual embed: {request.title[:50]}")
        success = await process_and_embed_article(
            canonical,
            request.title,
            request.content,
            request.source,
            session,
            request.category
        )
        
        if success:
            return {
                "success": True,
                "message": "Article successfully added to knowledge base"
            }
        else:
            return {
                "success": False,
                "error": "Failed to embed article"
            }
    except Exception as e:
        logger.error(f"Error embedding: {e}")
        return {"success": False, "error": str(e)}

async def process_and_embed_article(url: str, title: str, content: str, source: str, session: Session, category: str = "general"):
    """
    ✅ FIXED: Make summarization OPTIONAL to save API quota
    """
    try:
        canonical = canonical_url(url)
        logger.info(f"📝 RAG check: {canonical[:60]}")
        if is_homepage_link(canonical):
            logger.warning(f"⛔ Homepage rejected: {canonical}")
            return False
        
        if not is_valid_article_url(canonical, title):
            logger.warning(f"⛔ Invalid rejected: {canonical}")
            return False
        
        existing = session.query(NewsArticle).filter(NewsArticle.url == canonical).first()
        if existing:
            logger.info(f"✓ RAG hit: {title[:50]}")
            return True
        
        try:
            import unicodedata
            
            title_safe = title.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            title_safe = unicodedata.normalize('NFC', title_safe)
            
            content_safe = content.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            content_safe = unicodedata.normalize('NFC', content_safe)
            
            source_safe = source.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except Exception as enc_error:
            logger.error(f"❌ Encoding failed: {enc_error}")
            return False
        
        if len(content_safe) < 200:
            logger.warning(f"⚠️ Content too short ({len(content_safe)} chars): {title_safe[:50]}")
            return False
        
        if len(content_safe) > 2000:
            logger.info(f"🔄 Summarizing long content ({len(content_safe)} chars): {title_safe[:50]}...")
            summary = await summarize_article(canonical, title_safe, max_words=500)
            if not summary:
                logger.warning(f"⚠️ Summarization failed, using truncated content")
                # Use first 1000 chars instead
                summary = content_safe[:1000].strip()
                if not summary.endswith('.'):
                    last_period = summary.rfind('.')
                    if (last_period > 500):
                        summary = summary[:last_period + 1]
                    else:
                        summary += "..."
        else:
            logger.info(f"✅ Using content as-is ({len(content_safe)} chars) - no summarization needed")
            summary = content_safe
        
        logger.info(f"📊 Embedding: {title_safe[:50]}...")
        try:
            embedding_text = f"{title_safe}\n\n{summary}"
            embedding = await create_embedding(embedding_text)
            if not embedding or not isinstance(embedding, list) or len(embedding) != 384:
                logger.error(f"❌ Invalid embedding")
                embedding = [0.0] * 384
        except Exception as embed_error:
            logger.error(f"❌ Embedding failed: {embed_error}")
            embedding = [0.0] * 384
        
        language = 'vi' if any(ord(c) > 127 for c in title_safe) else 'en'
            
        try:
            metadata_dict = {
                "title": title_safe,
                "source": source_safe,
                "summary": summary,
                "url": canonical,
                "canonical_url": canonical,
                "category": category,
                "date": datetime.now().strftime('%Y-%m-%d'),
                "type": "news",
                "language": language,
                "title_hash": hash_title(title_safe)
            }
            metadata_str = json.dumps(metadata_dict, ensure_ascii=False)
            news_article = NewsArticle(
                title=title_safe[:500],
                content=summary,
                source=source_safe[:100],
                url=canonical[:1000],
                published_time=datetime.now(),
                language=language,
                embedding=embedding,
                meta_data=metadata_str
            )
            session.add(news_article)
            session.commit()
            logger.info(f"✅ RAG saved: {title_safe[:50]} (category={category})")
            return True
        except Exception as db_error:
            logger.error(f"❌ DB save failed: {db_error}")
            session.rollback()
            try:
                logger.info("🔄 Retrying minimal save...")
                news_article = NewsArticle(
                    title=title_safe[:255],
                    content=summary,
                    source=source_safe[:100],
                    url=canonical[:512],
                    published_time=datetime.now(),
                    language=language,
                    embedding=embedding,
                    meta_data=None
                )
                session.add(news_article)
                session.commit()
                logger.info("✅ Minimal save successful")
                return True
            except Exception as final_error:
                logger.error(f"❌ Final retry failed: {final_error}")
                session.rollback()
                return False
    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        session.rollback()
        return False

@router.get("/article/summary/{article_id}")
async def get_article_summary(
    article_id: str,
    session: Session = Depends(get_session)
):
    """Get article summary if already processed"""
    try:
        articles = session.query(NewsArticle).all()
        for article in articles:
            import hashlib
            url_hash = hashlib.md5(article.url.encode()).hexdigest()
            if url_hash == article_id:
                meta = json.loads(article.meta_data) if article.meta_data else {}
                return {
                    "success": True,
                    "summary": meta.get('summary', ''),
                    "title": article.title,
                    "source": article.source,
                    "url": article.url
                }
        return {
            "success": False,
            "message": "Article not yet processed"
        }
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return {"success": False, "error": str(e)}

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics - NOW USING DB CACHE"""
    try:
        from sqlalchemy import func
        session = next(get_session())
        try:
            article_count = session.query(func.count(NewsArticle.id)).scalar()
            return {
                "success": True,
                "stats": {
                    "total_cached": article_count or 0,
                    "max_capacity": "unlimited",
                    "ttl_days": 365
                }
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"success": False, "error": str(e)}

@router.post("/cache/clear")
async def clear_cache(session: Session = Depends(get_session)):
    """Clear news cache - CAREFUL: Deletes all articles from DB"""
    try:
        session.query(NewsArticle).delete()
        session.commit()
        return {"success": True, "message": "DB cache cleared"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        session.rollback()
        return {"success": False, "error": str(e)}

@router.post("/crawl")
async def crawl_news_deprecated():
    """Deprecated: Use /search instead"""
    return {
        "success": False,
        "message": "This endpoint is deprecated. Use GET /news/search?query=... instead"
    }

@router.get("/article/{article_id}")
async def get_full_article(
    article_id: str,
    url: str = Query(..., description="Article URL"),
    title: str = Query("", description="Article title"),
    session: Session = Depends(get_session)
):
    """
    DEPRECATED: This endpoint is no longer recommended
    Use /search instead which provides previews without crawling
    """
    try:
        existing = session.query(NewsArticle).filter(NewsArticle.url == url).first()
        if existing:
            return {
                "success": True,
                "article": {
                    "title": existing.title,
                    "content": existing.content,
                    "source": existing.source,
                    "url": existing.url,
                    "published_time": existing.published_time,
                    "summary": json.loads(existing.meta_data).get('summary', '') if existing.meta_data else ''
                }
            }
        
        return {
            "success": False,
            "message": "This endpoint is deprecated. Please use /news/search which provides article previews directly from APIs."
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"success": False, "error": str(e)}