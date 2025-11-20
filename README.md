# 📊 Financial Chatbot - AI-Powered Financial Assistant

A comprehensive financial assistant powered by LangChain, Google Gemini, and RAG (Retrieval-Augmented Generation) technology. Supports Vietnamese and US stock markets, gold prices, and multilingual financial news.

## 🌟 Key Features

- **💬 AI Chat Assistant**: Bilingual support (Vietnamese/English) with context-aware responses
- **📈 Stock Market Data**: 
  - Vietnamese stocks (VN-Index): Real-time quotes + historical data
  - US stocks (NASDAQ/NYSE): End-of-day data via EODHD API
  - Interactive charts: Candlestick, Technical indicators (RSI, MACD, Bollinger Bands)
- **💰 Gold Prices**: Live VN gold prices + international spot prices
- **📰 Financial News**: 
  - Multi-source aggregation (Tavily AI, NewsData.io, NewsAPI.org)
  - AI-powered summarization (Gemini 2.5 Flash)
  - RAG-based knowledge base with pgvector
- **🧠 Knowledge Base**: Vector search with multilingual embeddings (100+ languages)

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL with pgvector extension
- Gemini API key
- Tavily API key (for search capabilities)
- Internet connection for data fetching

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/financial-sp-chatbot.git
cd financial-sp-chatbot
```

### 2. Set up a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL with pgvector

Install PostgreSQL and the pgvector extension. Then run:

```bash
psql -U postgres -d postgres -c "CREATE DATABASE finance_bot;"
psql -U postgres -d finance_bot -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

After the database is set up, run the migration script:

```bash
psql -U postgres -d finance_bot -f migrations/setup_pgvector.sql
```

### 5. Configure environment variables

Create a `.env` file based on the example:

```bash
cp .env.example .env
```

Edit the `.env` file to include your API keys and database configuration:
- Set `DB_USERNAME` and `DB_PASSWORD` to your PostgreSQL credentials
- Add your `GOOGLE_API_KEY` for Gemini access
- Add your `TAVILY_API_KEY` for search capabilities

## 🏃‍♂️ Running the Application

### Start the backend API

```bash
cd financial-sp-chatbot
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

### Start the Streamlit UI

In a new terminal:

```bash
cd financial-sp-chatbot
streamlit run ui/streamlit_app.py
```

The UI will be available at http://localhost:8501

## 🔄 Initial Data Setup

When first running the application, you'll need to fetch initial data:

### Load Gold Prices
Click the "Update Gold Prices" button in the Gold Prices tab of the Streamlit UI, or make a request to:

```
GET http://localhost:8000/gold/update
```

### Add Stock Symbols
Use the "Add Symbol" feature in the Stock Prices tab and click "Update VN Stocks" or "Update US Stocks".

### Load News Articles
Click "Add News Source" in the News tab, or use the crawl-all endpoint:
```
GET http://localhost:8000/news/crawl-all
```

## 📚 API Documentation
Once the API is running, visit http://localhost:8000/docs for the Swagger UI documentation of all available endpoints.

Key Endpoints:

### Gold
- GET /gold/update: Fetch and store the latest gold prices
- GET /gold/latest: Get the most recent gold prices

### Stocks
- GET /stock/vn/update?symbols=VNIndex,FPT: Update Vietnamese stock prices
- GET /stock/us/update?symbols=AAPL,MSFT: Update US stock prices
- GET /stock/vn/{symbol}: Get data for a specific VN stock
- GET /stock/us/{symbol}: Get data for a specific US stock

### News
- GET /news/crawl-all: Crawl all configured RSS feeds
- GET /news/crawl?feed_url=URL&source_name=NAME: Crawl a specific RSS feed
- GET /news/query?query=SEARCH_TERM: Perform semantic search on stored news

### Chat
- POST /chat: Send a message to the chatbot

## 🧩 Project Structure
```
financial-sp-chatbot/
├── app/
│   ├── chains/         # LangChain components
│   ├── database/       # Database models and connection
│   ├── prompts/        # System prompts and templates
│   ├── rag/            # RAG components
│   ├── routers/        # FastAPI route definitions
│   └── services/       # Business logic services
├── migrations/         # Database migration scripts
├── ui/                 # Streamlit interface
└── requirements.txt    # Project dependencies
```
## API Testing
# Get all gold prices (VN + International)
curl http://localhost:8000/gold/prices

# VN gold only
curl http://localhost:8000/gold/prices/vn

# International gold only
curl http://localhost:8000/gold/prices/international

# Get single VN stock
curl http://localhost:8000/stocks/vn/VCB

# Update VN stocks (POST request)
curl -X POST http://localhost:8000/stocks/vn/update \
  -H "Content-Type: application/json" \
  -d '["VCB", "VHM", "FPT", "HPG", "TCB"]'

# Get VN stocks with charts (KEY ENDPOINT)
curl "http://localhost:8000/stocks/vn/charts?symbols=VCB,VHM,FPT&period=1mo"

# Batch get multiple VN stocks
curl "http://localhost:8000/stocks/vn/batch?symbols=VCB,VHM,FPT,HPG"

# Get single US stock
curl http://localhost:8000/stocks/us/AAPL

# Update US stocks (POST request)
curl -X POST http://localhost:8000/stocks/us/update \
  -H "Content-Type: application/json" \
  -d '["AAPL", "MSFT", "GOOGL", "AMZN"]'

# Get US stocks with charts (KEY ENDPOINT)
curl "http://localhost:8000/stocks/us/charts?symbols=AAPL,MSFT,GOOGL&period=1mo"

# Batch get multiple US stocks
curl "http://localhost:8000/stocks/us/batch?symbols=AAPL,MSFT,GOOGL,TSLA"

# Search news (English)
curl "http://localhost:8000/news/search?query=bitcoin&max_results=5&days=30"

# Search news (Vietnamese)
curl "http://localhost:8000/news/search?query=thị+trường+chứng+khoán&max_results=5&days=30"

# Search with URL encoding
curl "http://localhost:8000/news/search?query=gold+price+today&max_results=10&days=7"

# Track article click (POST - to embed into RAG)
curl -X POST "http://localhost:8000/news/article/track" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "url=https://example.com/article" \
  -d "title=Test Article" \
  -d "content=This is test content for embedding" \
  -d "source=TestSource"

# Get cache stats
curl http://localhost:8000/news/cache/stats

# Get knowledge statistics
curl http://localhost:8000/knowledge/stats

# Get recent news from RAG DB
curl "http://localhost:8000/knowledge/recent-news?limit=10"

# Search knowledge base (semantic search)
curl "http://localhost:8000/knowledge/search?query=gold+price&top_k=5"

# Send chat message
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current gold price?"}'

# Chat about stocks
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me info about VCB stock"}'

# Chat about news
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Latest news about Bitcoin"}'


# Direct Tavily search
curl "http://localhost:8000/search?query=VNINDEX+performance+2025"

## 📄 License
This project is for personal use only.