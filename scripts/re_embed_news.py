"""
Re-embed all news articles with new multilingual model
Run: python -m scripts.re_embed_news
"""
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import SessionLocal
from app.database.models import NewsArticle
from app.rag.embeddings import create_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def re_embed_all():
    """Re-embed all articles"""
    session = SessionLocal()
    
    try:
        # Get all articles
        articles = session.query(NewsArticle).all()
        
        logger.info(f"📦 Found {len(articles)} articles to re-embed")
        
        success = 0
        failed = 0
        
        for i, article in enumerate(articles, 1):
            try:
                logger.info(f"[{i}/{len(articles)}] Re-embedding: {article.title[:50]}")
                
                # Create new embedding
                text = f"{article.title}\n\n{article.content}"
                new_embedding = await create_embedding(text)
                
                if new_embedding and len(new_embedding) == 384:
                    article.embedding = new_embedding
                    success += 1
                else:
                    logger.error(f"❌ Invalid embedding for article {article.id}")
                    failed += 1
                
                # Commit every 10 articles
                if i % 10 == 0:
                    session.commit()
                    logger.info(f"✅ Committed batch (success={success}, failed={failed})")
                
            except Exception as e:
                logger.error(f"❌ Failed to re-embed article {article.id}: {e}")
                failed += 1
        
        # Final commit
        session.commit()
        
        logger.info(f"✅ Re-embedding complete!")
        logger.info(f"   Success: {success}")
        logger.info(f"   Failed: {failed}")
        
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(re_embed_all())
