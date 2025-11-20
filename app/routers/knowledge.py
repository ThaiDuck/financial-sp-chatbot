import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from ..database.connection import get_session
from ..database.models import NewsArticle, VNStock, USStock, GoldPrice
from ..services.news_service import semantic_search
import json
import numpy as np  # ✅ ADD: Missing import
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
    responses={404: {"description": "Not found"}},
)

@router.get("/stats")
async def get_knowledge_stats(session: Session = Depends(get_session)):
    """Get statistics about AI knowledge base"""
    try:
        news_count = session.query(func.count(NewsArticle.id)).scalar()
        
        # ✅ VERIFY: Count TOTAL rows (not distinct timestamps)
        vn_total = session.query(func.count(VNStock.id)).scalar()
        us_total = session.query(func.count(USStock.id)).scalar()
        
        gold_count = session.query(func.count(GoldPrice.id)).scalar()
        
        # ✅ Get latest gold price
        latest_gold = session.query(GoldPrice)\
            .order_by(GoldPrice.timestamp.desc())\
            .first()
        
        gold_info = None
        if latest_gold:
            gold_info = {
                "latest_price": f"{latest_gold.sell_price:,.0f} VND/gram",
                "source": latest_gold.source,
                "type": latest_gold.type,
                "timestamp": latest_gold.timestamp.isoformat()
            }
        
        # ✅ DEBUG: Log actual counts
        logger.info(f"📊 Knowledge stats: News={news_count}, VN={vn_total}, US={us_total}, Gold={gold_count}")
        
        # ✅ CRITICAL: Verify US stocks exist
        if us_total > 0:
            sample_us = session.query(USStock).limit(3).all()
            logger.info(f"   Sample US stocks: {[(s.symbol, s.timestamp) for s in sample_us]}")
        else:
            logger.warning("   ⚠️ No US stocks found in database!")
        
        return {
            "news_count": news_count or 0,
            "vn_stocks_count": vn_total or 0,
            "us_stocks_count": us_total or 0,
            "gold_count": gold_count or 0,
            "latest_gold": gold_info
        }
    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "news_count": 0,
            "vn_stocks_count": 0,
            "us_stocks_count": 0,
            "gold_count": 0,
            "latest_gold": None
        }

@router.get("/recent-news")
async def get_recent_news(
    limit: int = Query(20, description="Number of articles to return"),
    session: Session = Depends(get_session)
):
    """Get recent news articles from knowledge base"""
    try:
        articles = session.query(NewsArticle)\
            .order_by(NewsArticle.published_time.desc())\
            .limit(limit)\
            .all()
        
        result = []
        for article in articles:
            result.append({
                "id": article.id,
                "title": article.title,
                "content": article.content,
                "source": article.source,
                "url": article.url,
                "published_time": article.published_time.isoformat() if article.published_time else None,
                "language": article.language
            })
        
        return {"articles": result}
    except Exception as e:
        logger.error(f"Error getting recent news: {e}")
        return {"articles": []}

@router.get("/search")
async def search_knowledge_base(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(5, description="Number of results"),
    session: Session = Depends(get_session)
):
    """
    ✅ IMPROVED: Better logging + fallback
    """
    try:
        logger.info(f"🔍 Knowledge search: '{query}'")
        
        results = []
        
        # Check if query is about stocks
        stock_pattern = r'\b([A-Z]{2,5})\b'
        import re
        potential_symbols = re.findall(stock_pattern, query.upper())
        
        known_vn_stocks = ["VCB", "TCB", "BID", "VHM", "VIC", "HPG", "FPT", "VNM", "MSN", "GAS", "SAB"]
        known_us_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM"]
        
        found_vn_stocks = [s for s in potential_symbols if s in known_vn_stocks]
        found_us_stocks = [s for s in potential_symbols if s in known_us_stocks]
        
        # Query VN stocks
        if found_vn_stocks:
            cutoff = datetime.now() - timedelta(days=7)
            
            for symbol in found_vn_stocks:
                records = session.query(VNStock)\
                    .filter(VNStock.symbol == symbol)\
                    .filter(VNStock.timestamp >= cutoff)\
                    .order_by(VNStock.timestamp.desc())\
                    .limit(10)\
                    .all()
                
                if records:
                    latest = records[0]
                    oldest = records[-1]
                    
                    change = ((latest.close_price - oldest.close_price) / oldest.close_price) * 100
                    
                    results.append({
                        "type": "stock_vn",
                        "symbol": symbol,
                        "title": f"VN Stock: {symbol} (Last 7 days)",
                        "content": f"Latest price: {latest.close_price:,.0f} VND (Change: {change:+.2f}%). "
                                  f"High: {max(r.high for r in records):,.0f}, Low: {min(r.low for r in records):,.0f}, "
                                  f"Avg volume: {sum(r.volume for r in records)/len(records):,.0f}",
                        "source": "Database",
                        "published_time": latest.timestamp.isoformat(),
                        "similarity": 1.0
                    })
        
        # Query US stocks
        if found_us_stocks:
            cutoff = datetime.now() - timedelta(days=7)
            
            for symbol in found_us_stocks:
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
                    
                    results.append({
                        "type": "stock_us",
                        "symbol": symbol,
                        "title": f"US Stock: {symbol} (Last 7 days)",
                        "content": f"Latest price: ${latest.close_price:.2f} (Change: {change:+.2f}%). "
                                  f"High: ${max(r.high for r in records):.2f}, Low: ${min(r.low for r in records):.2f}, "
                                  f"Avg volume: {sum(r.volume for r in records)/len(records):,.0f}",
                        "source": "Database",
                        "published_time": latest.timestamp.isoformat(),
                        "similarity": 1.0
                    })
        
        # ✅ CRITICAL: Always try semantic search for news
        logger.info(f"📰 Searching news with semantic search...")
        news_results = await semantic_search(session, query, top_k)
        
        if news_results:
            logger.info(f"✅ Found {len(news_results)} news articles")
            results.extend(news_results)
        else:
            logger.warning(f"⚠️ No news articles found for: '{query}'")
            
            # ✅ DEBUG: Check database
            total_articles = session.query(func.count(NewsArticle.id)).scalar()
            with_embeddings = session.query(func.count(NewsArticle.id))\
                .filter(NewsArticle.embedding.isnot(None))\
                .scalar()
            
            logger.warning(f"   Database: {total_articles} total articles, {with_embeddings} with embeddings")
            
            # ✅ Try keyword fallback
            logger.info(f"📝 Trying keyword fallback...")
            keyword_query = f"%{query}%"
            keyword_results = session.query(NewsArticle)\
                .filter(
                    (NewsArticle.title.ilike(keyword_query)) |
                    (NewsArticle.content.ilike(keyword_query))
                )\
                .order_by(NewsArticle.published_time.desc())\
                .limit(top_k)\
                .all()
            
            if keyword_results:
                logger.info(f"✅ Keyword fallback found {len(keyword_results)} articles")
                for article in keyword_results:
                    results.append({
                        "type": "news",
                        "id": article.id,
                        "title": article.title,
                        "content": article.content[:300],
                        "source": article.source,
                        "url": article.url,
                        "published_time": article.published_time.isoformat(),
                        "similarity": 0.5  # Placeholder
                    })
        
        # Sort by similarity
        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        logger.info(f"✅ Total results: {len(results)}")
        
        return {"results": results[:top_k]}
        
    except Exception as e:
        logger.error(f"❌ Error searching knowledge base: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"results": []}

@router.get("/recent-gold")
async def get_recent_gold_prices(
    limit: int = Query(10, description="Number of records"),
    session: Session = Depends(get_session)
):
    """
    ✅ NEW: Get recent gold prices from database
    """
    try:
        records = session.query(GoldPrice)\
            .order_by(GoldPrice.timestamp.desc())\
            .limit(limit)\
            .all()
        
        result = []
        for record in records:
            result.append({
                "source": record.source,
                "type": record.type,
                "location": record.location,
                "buy_price": record.buy_price,
                "sell_price": record.sell_price,
                "timestamp": record.timestamp.isoformat()
            })
        
        return {"gold_prices": result}
    except Exception as e:
        logger.error(f"Error getting recent gold: {e}")
        return {"gold_prices": []}

@router.get("/debug/embeddings")
async def debug_embeddings(
    sample_text: str = Query("test", description="Sample text to embed"),
    session: Session = Depends(get_session)
):
    """
    ✅ NEW: Debug endpoint to test embedding system
    """
    try:
        from ..rag.embeddings import create_embedding
        
        # Test embedding
        embedding = await create_embedding(sample_text)
        
        # Check database
        total = session.query(func.count(NewsArticle.id)).scalar()
        with_emb = session.query(func.count(NewsArticle.id))\
            .filter(NewsArticle.embedding.isnot(None))\
            .scalar()
        
        # Get sample article
        sample = session.query(NewsArticle)\
            .filter(NewsArticle.embedding.isnot(None))\
            .first()
        
        return {
            "success": True,
            "query": {
                "text": sample_text,
                "embedding_length": len(embedding),
                "embedding_sample": embedding[:5],
                "magnitude": float(np.linalg.norm(embedding))
            },
            "database": {
                "total_articles": total,
                "with_embeddings": with_emb,
                "percentage": f"{(with_emb/total*100) if total > 0 else 0:.1f}%"
            },
            "sample_article": {
                "title": sample.title if sample else None,
                "has_embedding": sample.embedding is not None if sample else False,
                "embedding_length": len(sample.embedding) if sample and sample.embedding else 0
            } if sample else None
        }
    except Exception as e:
        logger.error(f"Debug error: {e}")
        return {"success": False, "error": str(e)}
