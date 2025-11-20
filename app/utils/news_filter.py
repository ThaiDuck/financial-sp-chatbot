import logging
from urllib.parse import urlparse, urlunparse
import re
import hashlib

logger = logging.getLogger(__name__)

HOMEPAGE_PATTERNS = [
    r'^https?://[^/]+/?$',
    r'^https?://[^/]+/index\.(html|php|aspx)$',
    r'^https?://[^/]+/(home|homepage|trang-chu)/?$',
    r'^https?://[^/]+/\d{4}/?$',
    r'^https?://[^/]+/(category|tag|archive|section)/?$',
]

HOMEPAGE_DOMAINS = [
    'vnexpress.net/',
    'cafef.vn/',
    'vietstock.vn/',
    'investing.com/',
    'reuters.com/',
    'bloomberg.com/',
]

def canonical_url(url: str) -> str:
    """
    Canonicalize URL to avoid duplicates
    - Remove mobile prefixes (m., mobile.)
    - Remove query params
    - Remove trailing slashes
    - Normalize scheme to https
    """
    try:
        parsed = urlparse(url)
        
        netloc = parsed.netloc.lower()
        netloc = re.sub(r'^(m\.|mobile\.|www\.)', '', netloc)
        
        path = parsed.path.rstrip('/')
        
        canonical = f"https://{netloc}{path}"
        
        logger.debug(f"Canonicalized: {url} → {canonical}")
        return canonical
        
    except Exception as e:
        logger.error(f"Error canonicalizing URL: {e}")
        return url

def hash_title(title: str) -> str:
    """
    Generate hash from normalized title for deduplication
    """
    normalized = title.lower().strip()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return hashlib.md5(normalized.encode()).hexdigest()

def is_homepage_link(url: str) -> bool:
    """Check if URL is likely a homepage/category page"""
    try:
        url_lower = url.lower()
        
        for pattern in HOMEPAGE_PATTERNS:
            if re.match(pattern, url_lower):
                logger.debug(f"Homepage pattern match: {url}")
                return True
        
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if not path or path.count('/') == 0:
            logger.debug(f"Empty or root path: {url}")
            return True
        
        for domain in HOMEPAGE_DOMAINS:
            if domain in url_lower and len(path) < 20:
                logger.debug(f"Short path on known domain: {url}")
                return True
        
        if path.startswith(('category/', 'tag/', 'section/', 'archive/')):
            logger.debug(f"Category/tag page: {url}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking homepage: {e}")
        return False

def is_valid_article_url(url: str, title: str = "") -> bool:
    """Check if URL is likely a real article"""
    if is_homepage_link(url):
        return False
    
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if len(path) < 10:
        logger.debug(f"Path too short: {url}")
        return False
    
    if not title or len(title) < 20:
        logger.debug(f"Title too short: {title}")
        return False
    
    article_indicators = [
        '.html',
        '-post-',
        '/news/',
        '/article/',
        '/story/',
        '/bai-viet/',
        '/tin-tuc/',
        r'/\d{4}/\d{2}/\d{2}/',
        r'/\d{8}/',
    ]
    
    for indicator in article_indicators:
        if re.search(indicator, url.lower()):
            return True
    
    if len(path) > 30 and path.count('-') > 2:
        return True
    
    return False

def extract_category(url: str, title: str) -> str:
    """
    Extract category from URL or title
    """
    url_lower = url.lower()
    title_lower = title.lower()
    
    categories = {
        'stock': ['stock', 'chứng khoán', 'cổ phiếu', 'thị trường', 'vnindex'],
        'gold': ['gold', 'vàng', 'kim loại'],
        'crypto': ['crypto', 'bitcoin', 'ethereum', 'blockchain'],
        'forex': ['forex', 'ngoại hối', 'currency'],
        'economy': ['economy', 'kinh tế', 'gdp', 'inflation'],
        'banking': ['bank', 'ngân hàng', 'credit', 'loan']
    }
    
    for category, keywords in categories.items():
        if any(kw in url_lower or kw in title_lower for kw in keywords):
            return category
    
    return 'general'
