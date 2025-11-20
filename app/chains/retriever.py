import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langchain.schema import Document
from langchain_community.vectorstores import PGVector
from langchain_community.embeddings import HuggingFaceEmbeddings
from sqlalchemy import text
from ..config import DATABASE_URL, TOP_K_RESULTS

logger = logging.getLogger(__name__)

# Hard-code the embedding model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Initialize the embedding model for LangChain
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

async def query_news(query, top_k=TOP_K_RESULTS, session=None):
    """
    Query news articles with metadata filtering and date awareness
    
    Args:
        query (str): Query text
        top_k (int): Number of results to return
        session: Database session
        
    Returns:
        List[Document]: List of retrieved documents
    """
    try:
        # Extract time-based filters from query
        time_filter = extract_time_filter(query)
        
        # Ensure query includes today's date to make model aware of current time
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        augmented_query = f"{query} (as of today: {today_str})"
        
        # Execute vector search with filtering
        if session:
            from ..services.news_service import semantic_search
            results = await semantic_search(
                session=session,
                query=augmented_query,
                top_k=top_k,
                filter_params=time_filter
            )
            
            # Convert to Documents
            docs = []
            for result in results:
                # Clean metadata
                metadata = {
                    "source": result.get("source", "Unknown"),
                    "title": result.get("title", "Untitled"),
                    "url": result.get("url", ""),
                    "published_time": result.get("published_time").strftime('%Y-%m-%d') if result.get("published_time") else today_str
                }
                
                # Create Document
                doc = Document(
                    page_content=result.get("content", ""),
                    metadata=metadata
                )
                docs.append(doc)
                
            return docs
            
        # Fallback to PGVector if needed
        else:
            # Create metadata filter
            metadata_filters = {}
            if time_filter.get('start_date'):
                metadata_filters["published_time"] = {"$gte": time_filter['start_date'].isoformat()}
            if time_filter.get('end_date'):
                if "published_time" not in metadata_filters:
                    metadata_filters["published_time"] = {}
                metadata_filters["published_time"]["$lte"] = time_filter['end_date'].isoformat()
            
            # Try to use PGVector with filtering
            try:
                vector_store = PGVector(
                    connection_string=DATABASE_URL,
                    embedding_function=embeddings,
                    collection_name="news_embeddings",
                    text_key="content",
                    embedding_key="embedding"
                )
                
                docs = vector_store.similarity_search(
                    augmented_query,
                    k=top_k,
                    filter=metadata_filters
                )
                
                return docs
                
            except Exception as e:
                logger.error(f"Error using PGVector: {e}")
                return []
        
    except Exception as e:
        logger.error(f"Error querying news with filtering: {e}")
        return []

def extract_time_filter(query):
    """
    Extract time-based filter from query text
    
    Args:
        query: User query string
        
    Returns:
        dict: Dictionary with start_date and end_date if found
    """
    filters = {}
    query_lower = query.lower()
    today = datetime.now().date()
    
    # Check for "recent" or "gần đây"
    if any(term in query_lower for term in ["recent", "gần đây", "lately", "this week", "tuần này", "tuần vừa qua"]):
        filters['start_date'] = datetime.combine(today - timedelta(days=7), datetime.min.time())
        filters['end_date'] = datetime.combine(today, datetime.max.time())
    
    # Check for "this month" or "tháng này"
    elif any(term in query_lower for term in ["this month", "tháng này", "tháng vừa qua"]):
        filters['start_date'] = datetime.combine(today.replace(day=1), datetime.min.time())
        filters['end_date'] = datetime.combine(today, datetime.max.time())
    
    # Check for year mentions
    elif "2023" in query_lower:
        filters['start_date'] = datetime(2023, 1, 1)
        filters['end_date'] = datetime(2023, 12, 31, 23, 59, 59)
    elif "2024" in query_lower:
        filters['start_date'] = datetime(2024, 1, 1)
        filters['end_date'] = datetime(2024, 12, 31, 23, 59, 59)
    
    # Ensure we're not returning future articles
    if 'end_date' in filters and filters['end_date'].date() > today:
        filters['end_date'] = datetime.combine(today, datetime.max.time())
    
    return filters
