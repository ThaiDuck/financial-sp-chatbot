import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
import google.generativeai as genai
from ..config import GOOGLE_API_KEY
import asyncio
import time

logger = logging.getLogger(__name__)

genai.configure(api_key=GOOGLE_API_KEY)

# ✅ FIXED: Use latest Gemini 3 Flash Preview model
STABLE_MODEL = "gemini-3-flash-preview"
EXPERIMENTAL_MODEL = "gemini-3-flash-preview"

# ✅ NEW: Track API usage to avoid rate limits
_last_api_call = 0
_min_interval = 2  # Minimum 2 seconds between calls

def extract_article_text(url: str) -> Optional[str]:
    """Extract full text from article URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            tag.decompose()
        
        article_selectors = [
            'article',
            '[class*="article"]',
            '[class*="content"]',
            '[class*="post-body"]',
            '[class*="entry-content"]',
            'main',
        ]
        
        article_text = None
        for selector in article_selectors:
            article = soup.select_one(selector)
            if article:
                paragraphs = article.find_all(['p', 'h1', 'h2', 'h3'])
                article_text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                if len(article_text) > 500:
                    break
        
        if not article_text:
            paragraphs = soup.find_all('p')
            article_text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
        
        if len(article_text) < 200:
            logger.warning(f"Extracted text too short: {len(article_text)} chars")
            return None
        
        logger.info(f"✅ Extracted {len(article_text)} chars from {url[:50]}")
        return article_text
        
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return None

async def summarize_article(url: str, title: str, max_words: int = 500) -> Optional[str]:
    """
    ✅ FIXED: Better rate limit handling + fallback to stable model
    """
    global _last_api_call
    
    try:
        # ✅ Rate limit protection
        time_since_last = time.time() - _last_api_call
        if time_since_last < _min_interval:
            await asyncio.sleep(_min_interval - time_since_last)
        
        full_text = extract_article_text(url)
        
        if not full_text:
            logger.warning(f"Could not extract text from {url}")
            return None
        
        # ✅ Try stable model first
        try:
            model = genai.GenerativeModel(STABLE_MODEL)
            
            prompt = f"""You are a financial news summarizer.

Article Title: {title}

Full Article Text:
{full_text[:8000]}

Task: Create a comprehensive summary (300-500 words) that captures:
1. Main topic/event and its significance
2. Key facts, figures, and statistics
3. Important context and background
4. Market implications and impact
5. Key stakeholder perspectives

Write in the same language as the article (Vietnamese or English).
Be objective, factual, and thorough. Use bullet points for clarity when appropriate."""

            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 1024,
                }
            )
            
            _last_api_call = time.time()
            
            summary = response.text.strip()
            
            if len(summary) < 100:
                logger.warning("Summary too short")
                return None
            
            logger.info(f"✅ Summarized: {title[:50]} ({len(summary)} chars, ~{len(summary.split())} words)")
            return summary
            
        except Exception as api_error:
            error_msg = str(api_error)
            
            # ✅ Handle rate limit
            if "429" in error_msg or "quota" in error_msg.lower():
                logger.warning(f"⚠️ Rate limit hit, returning snippet instead")
                
                # ✅ Fallback: Return first 500 words instead of failing
                words = full_text.split()[:500]
                fallback = " ".join(words)
                
                # Add ellipsis
                if len(words) == 500:
                    fallback += "..."
                
                return fallback
            
            # Other API errors
            logger.error(f"API error: {api_error}")
            return None
            
    except Exception as e:
        logger.error(f"Error summarizing: {e}")
        return None

async def summarize_article_direct(title: str, content: str, max_words: int = 500) -> Optional[str]:
    """
    ✅ NEW: Summarize from provided content (no URL fetching)
    
    This is for when we already have the content from search results.
    """
    global _last_api_call
    
    try:
        # ✅ Rate limit protection
        time_since_last = time.time() - _last_api_call
        if time_since_last < _min_interval:
            await asyncio.sleep(_min_interval - time_since_last)
        
        # ✅ CRITICAL: Use provided content directly
        full_text = content
        
        if not full_text or len(full_text) < 200:
            logger.warning(f"Content too short: {len(full_text)} chars")
            return None
        
        # ✅ Try stable model
        try:
            model = genai.GenerativeModel(STABLE_MODEL)
            
            prompt = f"""You are a financial news summarizer.

Article Title: {title}

Article Content:
{full_text[:8000]}

Task: Create a comprehensive summary (300-500 words) that captures:
1. Main topic/event and its significance
2. Key facts, figures, and statistics
3. Important context and background
4. Market implications and impact
5. Key stakeholder perspectives

Write in the same language as the article (Vietnamese or English).
Be objective, factual, and thorough. Use bullet points for clarity when appropriate."""

            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 1024,
                }
            )
            
            _last_api_call = time.time()
            
            summary = response.text.strip()
            
            if len(summary) < 100:
                logger.warning("Summary too short")
                return None
            
            logger.info(f"✅ Summarized: {title[:50]} ({len(summary)} chars)")
            return summary
            
        except Exception as api_error:
            error_msg = str(api_error)
            
            # ✅ Handle rate limit
            if "429" in error_msg or "quota" in error_msg.lower():
                logger.warning(f"⚠️ Rate limit hit, returning snippet")
                
                # Return first 500 words
                words = full_text.split()[:500]
                fallback = " ".join(words)
                
                if len(words) == 500:
                    fallback += "..."
                
                return fallback
            
            logger.error(f"API error: {api_error}")
            return None
            
    except Exception as e:
        logger.error(f"Error summarizing: {e}")
        return None

async def batch_summarize_articles(articles: List[Dict]) -> List[Optional[str]]:
    """
    Batch summarize multiple articles concurrently (3-5 at a time)
    """
    try:
        logger.info(f"📦 Batch summarizing {len(articles)} articles...")
        
        semaphore = asyncio.Semaphore(3)
        
        async def summarize_with_limit(article):
            async with semaphore:
                return await summarize_article(
                    article['url'],
                    article['title']
                )
        
        tasks = [summarize_with_limit(article) for article in articles]
        
        summaries = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for s in summaries if s and not isinstance(s, Exception))
        logger.info(f"✅ Batch summarized: {success_count}/{len(articles)} successful")
        
        return [s if s and not isinstance(s, Exception) else None for s in summaries]
        
    except Exception as e:
        logger.error(f"Error in batch summarization: {e}")
        return [None] * len(articles)
