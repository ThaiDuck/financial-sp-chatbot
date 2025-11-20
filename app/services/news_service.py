import logging
from sqlalchemy import text
from ..database.models import NewsArticle
from ..config import TOP_K_RESULTS
from ..rag.embeddings import create_embedding
import json

logger = logging.getLogger(__name__)

async def semantic_search(session, query, top_k=TOP_K_RESULTS, filter_params=None, category=None):
    """
    ✅ IMPROVED: With multilingual model, can use HIGHER threshold
    """
    try:
        # ✅ NO MORE QUERY EXPANSION (multilingual model handles it!)
        # Just normalize the query
        from ..rag.embeddings import _normalize_text
        
        vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        is_vietnamese = any(char in query.lower() for char in vietnamese_chars)
        language = "vietnamese" if is_vietnamese else "english"
        
        normalized_query = _normalize_text(query, language)
        
        logger.info(f"🔍 Semantic search ({language}): '{normalized_query[:100]}'")
        
        query_embedding = await create_embedding(normalized_query)
        
        if not query_embedding or len(query_embedding) != 384:
            logger.error(f"❌ Invalid query embedding")
            return []
        
        embedding_str = json.dumps(query_embedding)
        
        # ✅ IMPROVED: With multilingual model, use 0.35 threshold (35% similarity)
        # Old threshold: 0.2 (too low, noisy results)
        # New threshold: 0.35 (better precision)
        sql_base = """
            SELECT id, title, content, source, url, published_time, meta_data,
                   1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM news
            WHERE embedding IS NOT NULL
              AND (1 - (embedding <=> CAST(:embedding AS vector))) > 0.35
        """
        
        params = {"embedding": embedding_str}
        
        if category:
            sql_base += " AND meta_data::jsonb->>'category' = :category"
            params["category"] = category
        
        if filter_params:
            if filter_params.get('start_date'):
                sql_base += " AND published_time >= :start_date"
                params["start_date"] = filter_params['start_date']
            
            if filter_params.get('end_date'):
                sql_base += " AND published_time <= :end_date"
                params["end_date"] = filter_params['end_date']
        
        sql_final = sql_base + " ORDER BY similarity DESC LIMIT :limit"
        params["limit"] = top_k
        
        result = session.execute(text(sql_final), params)
        
        articles = []
        for row in result:
            articles.append({
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "source": row.source,
                "url": row.url,
                "published_time": row.published_time,
                "similarity": float(row.similarity),
                "metadata": json.loads(row.meta_data) if row.meta_data else {}
            })
        
        if articles:
            for i, a in enumerate(articles[:3]):
                logger.info(f"   [{i+1}] {a['title'][:50]}... (sim={a['similarity']:.1%})")
            
            avg_sim = sum(a['similarity'] for a in articles) / len(articles)
            logger.info(f"✅ RAG: {len(articles)} articles (avg similarity: {avg_sim:.1%})")
        else:
            logger.warning(f"⚠️ No articles above 35% similarity")
            
            total_count = session.execute(text("SELECT COUNT(*) FROM news WHERE embedding IS NOT NULL")).scalar()
            logger.warning(f"   Database: {total_count} articles with embeddings")
            
            # ✅ Show top 3 regardless of threshold
            test_result = session.execute(
                text("SELECT title, 1 - (embedding <=> CAST(:embedding AS vector)) as sim FROM news WHERE embedding IS NOT NULL ORDER BY sim DESC LIMIT 3"),
                {"embedding": embedding_str}
            )
            logger.warning(f"   Top 3 matches (no threshold):")
            for row in test_result:
                logger.warning(f"     - {row.title[:50]}... (sim={row.sim:.1%})")
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Semantic search error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

# ✅ KEEP: For chatbot RAG context
async def get_categorized_news(session, limit=20):
    """Get categorized news articles from DB (for display only)"""
    try:
        recent_articles = session.query(NewsArticle)\
            .order_by(NewsArticle.published_time.desc())\
            .limit(limit)\
            .all()
        
        if not recent_articles:
            return {"by_source": {}, "recent": []}
        
        sources = {}
        for article in recent_articles:
            source = article.source or "Unknown"
            if source not in sources:
                sources[source] = []
            if len(sources[source]) < limit:
                sources[source].append({
                    'id': article.id,
                    'title': article.title,
                    'content': article.content[:300] + "...",
                    'source': source,
                    'url': article.url,
                    'published_time': article.published_time,
                })
        
        return {
            "by_source": sources,
            "recent": recent_articles[:limit]
        }
    except Exception as e:
        logger.error(f"Error getting categorized news: {e}")
        return {"by_source": {}, "recent": []}