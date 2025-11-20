import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_USERNAME = os.getenv("DB_USERNAME", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "finance_bot")
DATABASE_URL = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ✅ FIXED: Load ALL API keys from .env (NO hardcoding!)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ✅ REMOVED: FMP API (no longer needed)
# ✅ NEW: EODHD API (100k calls/month FREE)
EODHD_API_KEY = os.getenv("EODHD_API_KEY")
EODHD_BASE_URL = "https://eodhd.com/api"

# ✅ Gold APIs
APISED_API_KEY = os.getenv("APISED_API_KEY")
APISED_BASE_URL = "https://gold.g.apised.com/v1"
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY")

# ✅ News APIs
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# ✅ Validate required keys
if not GOOGLE_API_KEY:
    print("❌ WARNING: GOOGLE_API_KEY not set. Chat features will not work.")

if not TAVILY_API_KEY:
    print("⚠️ WARNING: TAVILY_API_KEY not set. Search features limited.")

if not EODHD_API_KEY:
    print("⚠️ WARNING: EODHD_API_KEY not set. US stocks will not work.")
elif EODHD_API_KEY == "demo":
    print("⚠️ WARNING: Using EODHD demo key. Limited to 20 requests.")
else:
    print(f"✅ EODHD API key loaded: {EODHD_API_KEY[:10]}...")

if not NEWSDATA_API_KEY:
    print("⚠️ WARNING: NEWSDATA_API_KEY not set")
else:
    print(f"✅ NewsData.io key loaded: {NEWSDATA_API_KEY[:10]}...")

if not NEWSAPI_KEY:
    print("⚠️ WARNING: NEWSAPI_KEY not set")
else:
    print(f"✅ NewsAPI.org key loaded: {NEWSAPI_KEY[:10]}...")

# ✅ CRITICAL FIX: Use multilingual embedding model
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIMENSION = 384

# RAG settings
TOP_K_RESULTS = 5
