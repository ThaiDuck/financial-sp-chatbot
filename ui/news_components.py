import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from urllib.parse import urlparse
import re
import time
import random

# Common styling variables
CARD_BORDER_COLOR = "#e0e0e0"
CARD_SHADOW = "0 4px 6px rgba(0,0,0,0.1)"
CARD_MARGIN = "0 0 20px 0"

def load_css():
    """Load custom CSS for news display with improved styling"""
    css = """
    <style>
    /* News card styling - EVEN MORE COMPACT AND CLEAN */
    .news-card {
        border: 1px solid #e6e6e6;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 16px;
        display: flex;
        box-shadow: 0 2px 5px rgba(0,0,0,0.06);
        background-color: white;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .news-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .news-thumbnail {
        width: 100px;
        min-width: 100px;
        height: 100px;
        margin-right: 14px;
        border-radius: 6px;
        overflow: hidden;
        background-color: #f5f7fa;
    }
    .news-thumbnail img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .news-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .news-title {
        font-weight: 600;
        font-size: 16px;
        line-height: 1.4;
        margin-bottom: 6px;
        color: #1a1a1a;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
    }
    .news-source {
        display: flex;
        align-items: center;
        font-size: 12px;
        color: #606060;
        margin-bottom: 8px;
    }
    .source-name {
        font-weight: 500;
    }
    .news-source-logo {
        width: 14px;
        height: 14px;
        margin-right: 5px;
        border-radius: 2px;
    }
    .news-date {
        font-size: 11px;
        color: #707070;
    }
    .news-summary {
        font-size: 13px;
        line-height: 1.5;
        color: #444444;
        margin: 0 0 10px 0;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
    }
    .news-tags {
        display: flex;
        flex-wrap: wrap;
        margin-top: auto;
        gap: 6px;
    }
    .news-tag {
        font-size: 10px;
        color: #505050;
        background-color: #f0f2f5;
        border-radius: 10px;
        padding: 2px 8px;
    }
    /* ...other CSS rules... */
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def format_date(date_obj):
    """Format a date for display"""
    if not date_obj:
        return "Unknown date"
        
    today = datetime.now().date()
    
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                date_obj = datetime.strptime(date_obj, '%Y-%m-%d')
            except ValueError:
                return date_obj
    
    if isinstance(date_obj, datetime):
        article_date = date_obj.date()
        
        if article_date == today:
            # Format with hours if it's today
            return f"Today, {date_obj.strftime('%H:%M')}"
        elif article_date == today - timedelta(days=1):
            return "Yesterday"
        elif (today - article_date).days < 7:
            return date_obj.strftime('%A')  # Weekday name
        else:
            return date_obj.strftime('%d/%m/%Y')
    
    return "Unknown date"

def get_source_icon(url):
    """Get source icon URL based on domain"""
    if not url:
        return None
        
    try:
        domain = urlparse(url).netloc.lower()
        
        # Return favicon path based on domain
        if 'vnexpress.net' in domain:
            return "https://s.vnecdn.net/vnexpress/i/v20/logos/vne_logo_rss.png"
        elif 'cafef.vn' in domain:
            return "https://cafef.vn/images/logos/cafef-logo.png"
        elif 'ndh.vn' in domain:
            return "https://ndh.vn/apple-touch-icon.png"
        elif 'tinnhanhchungkhoan.vn' in domain:
            return "https://tinnhanhchungkhoan.vn/images/logoTNCK.png"
        elif 'vietstock.vn' in domain:
            return "https://vietstock.vn/Images/logo_vietstock.png"
        elif 'bloombergquint.com' in domain:
            return "https://www.bloombergquint.com/favicon.ico"
        elif 'investing.com' in domain:
            return "https://i-invdn-com.investing.com/logos/investing-com-logo.png"
        elif 'reuters.com' in domain:
            return "https://www.reuters.com/pf/resources/images/reuters/logo-vertical-default.png?d=151"
        elif 'cnbc.com' in domain:
            return "https://www.cnbc.com/favicon.ico"
        elif 'marketwatch.com' in domain:
            return "https://mw3.wsj.net/mw5/content/logos/mw_logo_social.png"
            
        # Default icon is the first letter of the domain
        first_letter = domain[0].upper() if domain else "N"
        return f"https://via.placeholder.com/16/3b5998/FFFFFF?text={first_letter}"
        
    except Exception as e:
        return "https://via.placeholder.com/16/cccccc/FFFFFF?text=N"

def format_source_name(source_url):
    """Format source name from URL"""
    if not source_url:
        return "Unknown"
        
    try:
        domain = urlparse(source_url).netloc.lower()
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Extract the main domain name
        main_parts = domain.split('.')
        if len(main_parts) >= 2:
            return main_parts[-2].capitalize()
        else:
            return domain.capitalize()
    except:
        return "Unknown"

def truncate_text(text, max_chars=250):
    """Truncate text with ellipsis"""
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."

def clean_news_text(text):
    """Clean news text by removing common garbage patterns"""
    if not text:
        return ""
        
    # First, handle HTML entities and tags
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'</?[a-z]+[^>]*>', '', text)  # Remove HTML tags but preserve content
    
    # Super aggressive cleaning - EXPANDED SIGNIFICANTLY
    garbage_patterns = [
        # Yahoo/Tavily specific garbage
        r"Oops,?\s+something\s+went\s+wrong\.?",
        r"Skip\s+to\s+(?:main\s+content|navigation|content|search|article).*?(?:\.|$)",
        r"News\s+Life\s+Entertainment\s+Finance\s+Sports.*?(?:\.|$)",
        r"Yahoo\s+(?:Finance|News|Mail).*?(?:\.|$)",
        r"Click\s+(?:here|this).*?(?:\.|$)",
        r"Error\s+loading.*?(?:\.|$)",
        r"External\s+Source.*?(?:\.|$)",
        r"JavaScript\s+is\s+(?:disabled|not\s+available).*?(?:\.|$)",
        r"Your\s+(?:browser|connection).*?(?:\.|$)",
        r"Press\s+(?:ESC|Escape).*?(?:\.|$)",
        r"Page\s+(?:not\s+found|unavailable).*?(?:\.|$)",
        
        # Common navigation elements
        r"Menu\s+(?:Home|About|Contact).*?(?:\.|$)",
        r"Sign\s+(?:in|up|out).*?(?:\.|$)",
        r"Log\s+(?:in|out).*?(?:\.|$)",
        r"Search\s+for.*?(?:\.|$)",
        r"Search\s+results.*?(?:\.|$)",
        r"Popular\s+searches.*?(?:\.|$)",
        r"(?:Latest|Top|Breaking)\s+(?:News|Stories).*?(?:\.|$)",
        
        # Common promotional text
        r"Subscribe\s+(?:now|today).*?(?:\.|$)",
        r"Get\s+(?:access|started|unlimited).*?(?:\.|$)",
        r"(?:Free|Premium)\s+(?:trial|subscription).*?(?:\.|$)",
        r"Join\s+(?:now|today|our).*?(?:\.|$)",
        r"Newsletter\s+(?:sign-?up|subscription).*?(?:\.|$)",
        r"Stay\s+(?:up-to-date|informed|connected).*?(?:\.|$)",
        r"Don't\s+miss.*?(?:\.|$)",
        
        # Common legal and disclaimer text
        r"(?:Terms|Conditions)\s+(?:of|and).*?(?:\.|$)",
        r"Privacy\s+(?:Policy|Notice|Statement).*?(?:\.|$)",
        r"Cookie\s+(?:Policy|Notice|Statement).*?(?:\.|$)",
        r"Copyright\s+\d{4}.*?(?:\.|$)",
        r"All\s+rights\s+reserved.*?(?:\.|$)",
        r"©\s*\d{4}.*?(?:\.|$)",
        r"Disclaimer.*?(?:\.|$)",
        
        # Footer and social media elements
        r"Follow\s+us\s+on.*?(?:\.|$)",
        r"Share\s+(?:on|this).*?(?:\.|$)",
        r"Connect\s+with\s+us.*?(?:\.|$)",
        r"Contact\s+(?:us|our).*?(?:\.|$)",
        r"(?:Facebook|Twitter|LinkedIn|Instagram).*?(?:\.|$)",
        
        # UI elements and buttons
        r"Click\s+(?:here|to).*?(?:\.|$)",
        r"Show\s+(?:more|less).*?(?:\.|$)",
        r"(?:Read|View|See)\s+(?:more|all).*?(?:\.|$)",
        r"Load\s+(?:more|next).*?(?:\.|$)",
        r"Back\s+to\s+(?:top|home).*?(?:\.|$)",
        r"(?:Next|Previous)\s+(?:page|article).*?(?:\.|$)",
        
        # Specific Yahoo Finance and Tavily patterns
        r"Quotes\s+are\s+powered\s+by.*?(?:\.|$)",
        r"Data\s+Disclaimer.*?(?:\.|$)",
        r"Data\s+(?:provided|sourced)\s+by.*?(?:\.|$)",
        r"(?:Live|Delayed)\s+quotes\s+by.*?(?:\.|$)",
        r"Symbol\s+lookup.*?(?:\.|$)",
        r"Recently\s+viewed.*?(?:\.|$)",
        r"Watchlist.*?(?:\.|$)",
        r"(?:1d|5d|1mo|3mo|6mo|1y|5y|max).*?(?:\.|$)",
        r"TRENDING.*?(?:\.|$)",
        r"TODAY.*?(?:\.|$)",
    ]
    
    # Apply all patterns to clean the text
    for pattern in garbage_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove excess whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove common endings that indicate truncation
    text = re.sub(r'Read More\.?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Show More\.?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Click to expand\.?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'View full article\.?$', '', text, flags=re.IGNORECASE)
    
    # Try to preserve sentence structure - end with a period if needed
    if text and text[-1] not in '.!?':
        text = text + '.'
    
    # Limit length - try to break at sentence boundaries
    if len(text) > 300:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) <= 300:
                summary += sentence + " "
            else:
                break
                
        if summary.strip():
            return summary.strip()
        else:
            # If we couldn't get complete sentences, just truncate
            return text[:297] + "..."
    
    return text

def extract_clean_image_url(article):
    """Extract and validate image URL from article with improved extraction"""
    image_url = article.get('image_url')
    
    # If no image URL or it's None/null string
    if not image_url or str(image_url).lower() in ('none', 'null', ''):
        # Check for og:image meta tag in content first (common in HTML)
        content = article.get('content', '')
        og_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](https?://[^"\']+)["\']', content)
        if og_match:
            image_url = og_match.group(1)
        else:
            # Try to find any image tag
            img_match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', content)
            if img_match:
                image_url = img_match.group(1)
            else:
                # Generate placeholder based on source
                source = article.get('source', '')
                url = article.get('url', '')
                
                # Try to get favicon from the source domain
                if url:
                    try:
                        domain = urlparse(url).netloc
                        favicon_url = f"https://{domain}/favicon.ico"
                        # Use a more informative placeholder with the first letter of the source
                        first_letter = (source or domain)[0].upper() if source or domain else "N"
                        image_url = f"https://via.placeholder.com/120x120/e0e7ff/1a56db?text={first_letter}"
                    except:
                        image_url = "https://via.placeholder.com/120x120/e0e7ff/1a56db?text=📰"
                else:
                    image_url = "https://via.placeholder.com/120x120/e0e7ff/1a56db?text=📰"
    
    # Filter out known problematic image URLs
    problem_patterns = [
        r'spacer\.gif',
        r'blank\.gif',
        r'pixel\.gif',
        r'empty\.gif',
        r'transparent\.gif',
        r'1x1\.gif',
        r'placeholder\.jpg',
        r'placeholder\.png',
        r'empty\.jpg',
        r'spacer\.png',
        r'logo\.png'
    ]
    
    for pattern in problem_patterns:
        if re.search(pattern, image_url, re.IGNORECASE):
            return "https://via.placeholder.com/120x120/e0e7ff/1a56db?text=📰"
    
    # Validate URL format
    try:
        parsed = urlparse(image_url)
        if not all([parsed.scheme, parsed.netloc]) or parsed.scheme not in ('http', 'https'):
            return "https://via.placeholder.com/120x120/e0e7ff/1a56db?text=📰"
    except:
        return "https://via.placeholder.com/120x120/e0e7ff/1a56db?text=📰"
        
    return image_url

def normalize_news_article(article):
    """Normalize news article to ensure consistent format"""
    if not article:
        return None
        
    # Clean and normalize title
    title = article.get('title', 'No title available')
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = title[:97] + '...'
        
    # Clean and normalize content - MUCH more aggressive cleaning
    content = article.get('content', 'No content available')
    clean_content = clean_news_text(content)
    
    # Check for minimum content quality
    if len(clean_content) < 50 or any(term in clean_content.lower() for term in ["oops", "skip to", "error loading"]):
        clean_content = "" 
    
    # Get clean source and format date
    source = article.get('source', 'Unknown')
    if source == 'Unknown' or source == 'External Source':
        url = article.get('url', '')
        source = format_source_name(url)
    
    # Format date
    published_time = article.get('published_time')
    formatted_date = format_date(published_time)
    
    # Get categories and deduplicate them
    categories = article.get('categories', [])
    if not isinstance(categories, list):
        categories = []
    # Convert category strings to title case and deduplicate
    categories = list(set(cat.title() for cat in categories if cat))[:3]  # Limit to top 3 categories
    
    # Extract clean image URL
    image_url = extract_clean_image_url(article)
    
    # Create normalized article
    return {
        'title': title,
        'content': clean_content,
        'source': source,
        'url': article.get('url', '#'),
        'published_time': published_time,
        'formatted_date': formatted_date,
        'image_url': image_url,
        'categories': categories,
        'similarity': article.get('similarity', 0),
        'highlighted_title': article.get('highlighted_title', title),
        'highlighted_content': article.get('highlighted_content', clean_content[:250] + ('...' if len(clean_content) > 250 else ''))
    }

def render_news_card(article):
    """Render a single news article as a card"""
    # First normalize the article data
    norm_article = normalize_news_article(article)
    if not norm_article:
        return ""
        
    # Extract normalized fields
    title = norm_article['title']
    content = norm_article['highlighted_content']
    source = norm_article['source']
    url = norm_article['url']
    formatted_date = norm_article['formatted_date']
    image_url = norm_article['image_url']
    categories = norm_article['categories']
    
    # Extra security check - truncate very long titles
    if len(title) > 100:
        title = title[:97] + "..."
        
    # Minimum quality check - don't show cards with garbage content
    if len(content) < 30 or content.lower().startswith("oops") or "skip to" in content.lower():
        content = ""
    
    # Create a more compact card with less content when appropriate
    if content:
        content_html = f'<div class="news-summary">{content}</div>'
    else:
        content_html = ""
    
    # Generate HTML with improved styling and error handling
    card_html = f"""
    <div class="news-card">
        <div class="news-thumbnail">
            <img src="{image_url}" alt="{source}" onerror="this.src='https://via.placeholder.com/100x100?text=📰'">
        </div>
        <div class="news-content">
            <a href="{url}" target="_blank" style="text-decoration: none; color: inherit;">
                <div class="news-title">{title}</div>
            </a>
            <div class="news-source">
                <img class="news-source-logo" src="{get_source_icon(url)}" alt="{source}">
                <span class="source-name">{source}</span> · <span class="news-date">{formatted_date}</span>
            </div>
            {content_html}
            <div class="news-tags">
                {' '.join([f'<span class="news-tag">{cat}</span>' for cat in categories[:3]])}
            </div>
        </div>
    </div>
    """
    
    return card_html

def render_news_list(articles, page=1, items_per_page=5):
    """Render a list of news articles with pagination and improved styling"""
    if not articles:
        empty_state_html = """
        <div class="empty-state">
            <img src="https://via.placeholder.com/80x80?text=📰" alt="No results">
            <h3>No news articles found</h3>
            <p>Try a different search term or check back later for new articles.</p>
        </div>
        """
        st.markdown(empty_state_html, unsafe_allow_html=True)
        return
        
    # Preprocess and normalize all articles before rendering
    normalized_articles = []
    for article in articles:
        norm_article = normalize_news_article(article)
        if norm_article:  # Only include valid articles
            normalized_articles.append(norm_article)
    
    # If no valid articles after normalization
    if not normalized_articles:
        st.warning("No valid news articles found. Try a different search.")
        return
        
    # Calculate pagination
    total_items = len(normalized_articles)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    # Adjust page if out of bounds
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
        
    # Get items for current page
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_page_items = normalized_articles[start_idx:end_idx]
    
    # Render articles using the original articles to preserve all data
    all_cards_html = ""
    for article_idx in range(start_idx, end_idx):
        if article_idx < len(articles):
            all_cards_html += render_news_card(articles[article_idx])
    
    # Render all cards
    st.markdown(all_cards_html, unsafe_allow_html=True)
    
    # Show pagination controls if needed
    if total_pages > 1:
        col1, col2, col3, col4, col5 = st.columns([1, 1, 3, 1, 1])
        
        with col1:
            if st.button("⏪ First", disabled=(page == 1)):
                st.session_state.news_page = 1
                st.rerun()
                
        with col2:
            if st.button("⬅️ Prev", disabled=(page == 1)):
                st.session_state.news_page = page - 1
                st.rerun()
                
        with col3:
            st.markdown(f"<div style='text-align: center'>Page {page} of {total_pages}</div>", unsafe_allow_html=True)
            
        with col4:
            if st.button("Next ➡️", disabled=(page == total_pages)):
                st.session_state.news_page = page + 1
                st.rerun()
                
        with col5:
            if st.button("Last ⏩", disabled=(page == total_pages)):
                st.session_state.news_page = total_pages
                st.rerun()
    
    # Show total article count
    st.caption(f"Showing {len(current_page_items)} of {total_items} articles")

def render_news_filters():
    """Render filter controls for news"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date filter
        date_filter = st.selectbox(
            "Date", 
            ["All time", "Today", "This week", "This month", "This year"],
            key="news_date_filter"
        )
    
    with col2:
        # Source filter
        source_filter = st.multiselect(
            "Source",
            ["VnExpress", "CafeF", "Vietstock", "CNBC", "Reuters", "Bloomberg"],
            key="news_source_filter"
        )
    
    with col3:
        # Category filter
        category_filter = st.multiselect(
            "Category",
            ["Chứng khoán", "Ngân hàng", "Vàng", "BĐS", "Ngoại hối", "Crypto"],
            key="news_category_filter"
        )
        
    # Sort control
    sort_option = st.radio(
        "Sort by",
        ["Newest first", "Relevance"],
        horizontal=True,
        key="news_sort"
    )
    
    return {
        "date": date_filter,
        "sources": source_filter,
        "categories": category_filter,
        "sort": sort_option
    }

def filter_articles(articles, filters):
    """Apply filters to articles"""
    if not articles:
        return []
        
    filtered_articles = articles.copy()
    
    # Date filtering
    if filters["date"] != "All time":
        today = datetime.now().date()
        
        if filters["date"] == "Today":
            filtered_articles = [a for a in filtered_articles 
                                if a.get('published_time') and a.get('published_time').date() == today]
        elif filters["date"] == "This week":
            start_of_week = today - timedelta(days=today.weekday())
            filtered_articles = [a for a in filtered_articles 
                                if a.get('published_time') and a.get('published_time').date() >= start_of_week]
        elif filters["date"] == "This month":
            start_of_month = today.replace(day=1)
            filtered_articles = [a for a in filtered_articles 
                                if a.get('published_time') and a.get('published_time').date() >= start_of_month]
        elif filters["date"] == "This year":
            start_of_year = today.replace(month=1, day=1)
            filtered_articles = [a for a in filtered_articles 
                                if a.get('published_time') and a.get('published_time').date() >= start_of_year]
    
    # Source filtering
    if filters["sources"]:
        filtered_articles = [a for a in filtered_articles 
                            if a.get('source') in filters["sources"] or 
                            any(s.lower() in a.get('url', '').lower() for s in filters["sources"])]
    
    # Category filtering
    if filters["categories"]:
        filtered_articles = [a for a in filtered_articles 
                            if any(c in a.get('categories', []) for c in filters["categories"])]
    
    # Sorting
    if filters["sort"] == "Newest first":
        filtered_articles = sorted(filtered_articles, 
                                key=lambda x: x.get('published_time', datetime.min), 
                                reverse=True)
    else:
        # Sort by relevance (similarity score)
        filtered_articles = sorted(filtered_articles, 
                                key=lambda x: x.get('similarity', 0), 
                                reverse=True)
    
    return filtered_articles

def render_loading_animation():
    """Show loading animation while waiting for news results"""
    loading_html = """
    <div class="news-loader">
        <img src="https://via.placeholder.com/32x32?text=⌛" alt="Loading..." width="32" height="32">
        <span style="margin-left: 10px; color: #606060;">Searching for news...</span>
    </div>
    """
    return st.markdown(loading_html, unsafe_allow_html=True)
