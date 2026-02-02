import logging
import weakref
import atexit

# ✅ FIX: Patch weakref.finalize to prevent "dictionary changed size during iteration" error
def _safe_finalize_atexit():
    """Safe atexit cleanup that handles dictionary iteration errors"""
    try:
        # Make a snapshot of pending finalizers to avoid iteration issues
        pending = []
        try:
            registry_items = list(weakref.finalize._registry.items())
            pending = [(f, i) for (f, i) in registry_items if i.atexit]
        except (RuntimeError, AttributeError):
            # Dictionary changed during iteration or no registry - skip
            pass
        
        # Sort by index (LIFO order) and call
        pending.sort(key=lambda x: x[1].index, reverse=True)
        
        for f, _ in pending:
            try:
                f()
            except Exception:
                pass
    except Exception:
        pass

# Apply patch early before other imports
try:
    if hasattr(weakref.finalize, '_exitfunc'):
        # Store original and replace with safe version
        weakref.finalize._original_exitfunc = weakref.finalize._exitfunc
        weakref.finalize._exitfunc = classmethod(lambda cls: _safe_finalize_atexit())
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import sys

# Make sure we load environment variables before anything else
load_dotenv()

from .routers import gold, news, chat, health, knowledge
from .routers.stocks import router as stocks_router
from .database.connection import init_db, wait_for_db

# Log some diagnostic info about API keys (without revealing full keys)
polygon_key = os.getenv("POLYGON_API_KEY")
if polygon_key:
    safe_key = polygon_key[:5] + "..." if len(polygon_key) > 5 else "invalid"
    logging.info(f"Loaded Polygon API key starting with: {safe_key}")
else:
    logging.warning("No Polygon API key found in environment")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validate required environment variables
required_keys = ["GOOGLE_API_KEY"]
for key in required_keys:
    if not os.getenv(key):
        logger.warning(f"Missing environment variable: {key}")

# Initialize FastAPI app
app = FastAPI(
    title="Financial Chatbot API",
    description="Real-time financial data + AI-powered insights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ CRITICAL: Include stocks router with proper prefix
# This ensures /vn/charts is registered before /vn/{symbol}
app.include_router(stocks_router, tags=["stocks"])

# Include other routers
app.include_router(gold.router, tags=["gold"])
app.include_router(news.router, tags=["news"])
app.include_router(chat.router, tags=["chat"])
app.include_router(health.router, tags=["health"])
app.include_router(knowledge.router, tags=["knowledge"])

# Add a search endpoint to the root app to handle Tavily search requests
from .services.tavily_service import TavilySearch

@app.get("/search", tags=["search"])
async def search(query: str = Query(..., description="Search query")):
    """Search for information using Tavily API"""
    try:
        result = await TavilySearch.search_financial_news(query)
        # Check for error in the result
        if "error" in result and result["error"]:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks"""
    try:
        # ✅ NEW: Clear old EODHD failed cache on startup
        from pathlib import Path
        import time
        
        cache_dir = Path("cache/eodhd")
        if cache_dir.exists():
            failed_files = list(cache_dir.glob("*_failed.txt"))
            
            now = time.time()
            cleared = 0
            
            for f in failed_files:
                # Clear if older than 30 minutes
                if now - f.stat().st_mtime > 1800:
                    f.unlink()
                    cleared += 1
            
            if cleared > 0:
                logger.info(f"🧹 Cleared {cleared} old failed cache files")
        
        # Wait for database
        if not wait_for_db(max_retries=12, retry_interval=5):
            logger.warning("Could not connect to database")
        else:
            init_db()
            logger.info("Database initialized")
        
    except Exception as e:
        logger.warning(f"Startup warning: {e}")
        # Don't fail startup, allow degraded mode

@app.get("/", tags=["status"])
async def root():
    return {"message": "Financial Chatbot API is running"}

@app.get("/health", tags=["status"])
async def health_check():
    """Health check endpoint for Docker"""
    return {"status": "ok"}

# Add a diagnostic endpoint to help troubleshoot API issues
from .utils.api_diagnose import run_all_api_tests

@app.get("/diagnostic/api-test", tags=["diagnostic"])
async def test_api_connections():
    """Test connections to external APIs"""
    results = run_all_api_tests()
    return results

# Main function to run app with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
