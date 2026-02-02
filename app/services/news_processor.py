"""
News processing pipeline:
1. Crawl RSS
2. Parse & Clean
3. Smart Chunk
4. Generate Summary (via LLM)
5. Create Embeddings
6. Save to DB
"""

from typing import List, Dict
import asyncio
from ..rag.embeddings import create_embedding
from ..database.models import NewsArticle
import logging

logger = logging.getLogger(__name__)

class NewsProcessor:
    """Process news: summarize, chunk, embed optimally"""
    
    @staticmethod
    async def process_article(article: Dict) -> Dict:
        """Process single article: clean → chunk → embed"""
        try:
            # 1. Extract & clean content
            content = article.get('content', '')
            title = article.get('title', '')
            
            # 2. Generate summary using LLM (async)
            summary = await NewsProcessor.summarize(title, content[:1000])
            
            # 3. Smart chunking
            chunks = NewsProcessor.smart_chunk(content, max_tokens=512)
            
            # 4. Create embeddings for each chunk
            chunk_embeddings = []
            for chunk in chunks:
                # Embed with title + summary for context
                embedding_text = f"{title}. {summary}\n\n{chunk}"
                embedding = await create_embedding(embedding_text)
                chunk_embeddings.append(embedding)
            
            return {
                "title": title,
                "summary": summary,  # ← NEW: Add summary
                "chunks": chunks,
                "embeddings": chunk_embeddings,
                "source": article.get('source'),
                "url": article.get('url'),
                "published_time": article.get('published_time'),
                "language": article.get('language', 'en')
            }
        except Exception as e:
            logger.error(f"Error processing article: {e}")
            return None
    
    @staticmethod
    async def summarize(title: str, content: str, max_length: int = 150) -> str:
        """Generate summary using LLM"""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from ..config import GOOGLE_API_KEY
            
            llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                google_api_key=GOOGLE_API_KEY,
                temperature=0.2,
                max_tokens=200
            )
            
            prompt = f"""Summarize this news in max 150 chars for quick preview:

Title: {title}
Content: {content}

Summary (max 150 chars, no title):"""
            
            response = await llm.ainvoke(prompt)
            return response.content.strip()[:150]
        except Exception as e:
            logger.error(f"Error summarizing: {e}")
            return content[:100] + "..."
    
    @staticmethod
    def smart_chunk(text: str, max_tokens: int = 512, overlap_ratio: float = 0.2) -> List[str]:
        """Smart chunking: respects paragraphs, sentences"""
        from nltk.tokenize import sent_tokenize
        import nltk
        
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        # Split into sentences
        sentences = sent_tokenize(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        overlap_text = ""
        
        for sentence in sentences:
            sentence_length = len(sentence.split())
            
            if current_length + sentence_length > max_tokens:
                # Save chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)
                
                # Create overlap
                overlap_sentences = int(len(current_chunk) * overlap_ratio)
                overlap_text = " ".join(current_chunk[-overlap_sentences:]) if overlap_sentences > 0 else ""
                
                # Start new chunk with overlap
                current_chunk = overlap_text.split() if overlap_text else []
                current_length = len(current_chunk)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
