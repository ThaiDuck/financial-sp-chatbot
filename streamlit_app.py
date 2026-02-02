import streamlit as st
import requests
import os
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time  # ✅ ADD: Missing import

st.set_page_config(page_title="Financial Chatbot", page_icon="📈", layout="wide")

# API Base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

# Sidebar - API Status & Controls
with st.sidebar:
    st.subheader("⚙️ API Status")
    
    # Check API health
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_response.status_code == 200:
            st.success("✓ FastAPI: Connected")
        else:
            st.error("✗ FastAPI: Error")
    except:
        st.error("✗ FastAPI: Disconnected")
    
    st.divider()
    
    # Data Management Section
    st.subheader("📊 Data Management")
    
    if st.button("🔄 Crawl Gold Prices", use_container_width=True):
        with st.spinner("Fetching gold prices..."):
            try:
                response = requests.get(f"{API_BASE_URL}/gold/prices")
                if response.status_code == 200:
                    st.success("✓ Gold prices updated!")
                    st.rerun()
                else:
                    st.error("Failed to fetch gold prices")
            except Exception as e:
                st.error(f"Error: {e}")
    
    if st.button("📈 Update VN Stocks", use_container_width=True):
        with st.spinner("Updating VN stocks..."):
            try:
                symbols = ["VCB", "VHM", "VIC", "HPG", "TCB", "FPT", "MSN", "VNM", "GAS", "SAB"]
                response = requests.post(
                    f"{API_BASE_URL}/stocks/vn/update",
                    json=symbols
                )
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✓ Updated {data.get('records', 0)} VN stock records")
                    st.rerun()
                else:
                    st.error("Failed to update VN stocks")
            except Exception as e:
                st.error(f"Error: {e}")
    
    if st.button("🇺🇸 Update US Stocks", use_container_width=True):
        with st.spinner("Updating US stocks..."):
            try:
                symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM"]
                response = requests.post(
                    f"{API_BASE_URL}/stocks/us/update",
                    json=symbols
                )
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✓ Updated {data.get('records', 0)} US stock records")
                    st.rerun()
                else:
                    st.error("Failed to update US stocks")
            except Exception as e:
                st.error(f"Error: {e}")

# Main UI - Tabs (ADD AI Knowledge tab)
st.title("📊 Financial Chatbot")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💬 Chat", 
    "💰 Gold Prices", 
    "📈 VN Stocks", 
    "🇺🇸 US Stocks", 
    "📰 News",
    "🧠 AI Knowledge" 
])

# Tab 1: Chat
with tab1:
    st.markdown("### AI Financial Assistant")
    
    # ✅ Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"streamlit_{int(time.time())}"  # ✅ Now works
    
    # ✅ Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # ✅ Chat input
    if user_input := st.chat_input("Ask about gold, stocks, or news..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Processing..."):
                try:
                    # ✅ Send with session ID
                    response = requests.post(
                        f"{API_BASE_URL}/chat/message",
                        json={
                            "message": user_input,
                            "session_id": st.session_state.session_id  # ✅ Include session
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        assistant_response = data.get("response", "No response")
                        
                        # ✅ Update session ID if returned
                        if "session_id" in data:
                            st.session_state.session_id = data["session_id"]
                        
                        st.write(assistant_response)
                        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    else:
                        st.error(f"Error: API returned status {response.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # ✅ Add clear button in sidebar
    with st.sidebar:
        st.divider()
        st.subheader("💬 Chat Session")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                try:
                    # Clear on backend
                    requests.post(
                        f"{API_BASE_URL}/chat/clear",
                        params={"session_id": st.session_state.session_id},
                        timeout=5
                    )
                except:
                    pass
                
                # Clear local state
                st.session_state.messages = []
                st.session_state.session_id = f"streamlit_{int(time.time())}"
                st.rerun()
        
        with col2:
            msg_count = len(st.session_state.messages)
            st.metric("Messages", msg_count)

# Tab 2: Gold Prices Visualization
with tab2:
    st.markdown("### 💰 Current Gold Prices")
    
    try:
        response = requests.get(f"{API_BASE_URL}/gold/prices")
        if response.status_code == 200:
            gold_data = response.json()["data"]
            
            # VN Gold Prices
            st.subheader("🇻🇳 Vietnam Gold Prices (VND/gram)")
            vn_gold = gold_data.get("vn", [])
            
            if vn_gold:
                df_vn = pd.DataFrame(vn_gold)
                
                # ✅ Show price for each gold type
                cols = st.columns(min(len(vn_gold), 3))
                
                for idx, gold_item in enumerate(vn_gold):
                    with cols[idx % 3]:
                        gold_type = gold_item.get('type', 'Unknown')
                        buy_price = gold_item.get('buy_price', 0)
                        sell_price = gold_item.get('sell_price', 0)
                        
                        st.metric(
                            gold_type,
                            f"Buy: {buy_price:,.0f} ₫/g"
                        )
                        st.caption(f"Sell: {sell_price:,.0f} ₫/g")
                        
                        # ✅ Show change if available (only for 24K)
                        if 'details' in gold_item:
                            details = gold_item['details']
                            change_pct = details.get('change_pct', 0)
                            if change_pct != 0:
                                st.caption(f"Change: {change_pct:+.2f}%")
                
                st.divider()
                
                # Show table
                display_cols = ['source', 'type', 'buy_price', 'sell_price', 'location']
                st.dataframe(
                    df_vn[display_cols],
                    use_container_width=True
                )
                
                # ✅ Show market info if available
                if vn_gold[0].get('details'):
                    details = vn_gold[0]['details']
                    
                    st.subheader("📊 Today's Market Stats (24K)")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Open", f"{details.get('open', 0):,.0f} ₫")
                    with col2:
                        st.metric("High", f"{details.get('high', 0):,.0f} ₫")
                    with col3:
                        st.metric("Low", f"{details.get('low', 0):,.0f} ₫")
                    with col4:
                        change = details.get('change', 0)
                        st.metric("Change", f"{change:+,.0f} ₫")
                
            else:
                st.info("No VN gold data available. Click 'Crawl Gold Prices' to fetch.")
            
            # International Gold Prices
            st.subheader("🌍 International Gold Prices")
            intl_gold = gold_data.get("international", [])
            
            if intl_gold:
                df_intl = pd.DataFrame(intl_gold)
                
                # Show latest price
                latest_price = df_intl['price_usd'].iloc[0]
                st.metric("Gold Spot Price", f"${latest_price:,.2f}/oz")
                
                # Show details
                display_cols = ['source', 'type', 'price_usd', 'high_24h', 'low_24h', 'open']
                st.dataframe(
                    df_intl[display_cols],
                    use_container_width=True
                )
            else:
                st.info("No international gold data available.")
        else:
            st.error("Failed to fetch gold prices")
    except Exception as e:
        st.error(f"Error: {e}")

# Tab 3: VN Stocks
with tab3:
    st.markdown("### 📈 Vietnam Stock Market")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        default_symbols = "VCB,VHM,VIC,FPT,HPG,VNM"
        symbols_input = st.text_input(
            "Enter stock symbols (comma-separated):", 
            default_symbols,
            help="Example: VCB,VHM,FPT",
            key="vn_symbols"
        )
    with col2:
        # ✅ FIXED: Add 1d and 1w options
        period = st.selectbox(
            "Period:", 
            ["1d", "1w", "1mo", "3mo", "6mo", "1y"],  # ✅ More options
            index=2,  # Default to "1mo"
            key="vn_period"
        )
    
    # ✅ Show info about data granularity
    period_info = {
        "1d": "📊 Intraday data (hourly intervals)",
        "1w": "📅 Daily data for 1 week",
        "1mo": "📅 Daily data for 1 month",
        "3mo": "📅 Daily data for 3 months",
        "6mo": "📆 Weekly data for 6 months",
        "1y": "📆 Weekly data for 1 year"
    }
    
    if period in period_info:
        st.caption(period_info[period])
    
    # ✅ STAGING: Auto-load data when tab is opened
    if "vn_stocks_loaded" not in st.session_state:
        st.session_state.vn_stocks_loaded = False
    
    # ✅ IMPORTANT: Only fetch if symbols changed or first load
    current_vn_symbols = symbols_input.strip().upper()
    current_vn_period = period
    
    # Check if we need to refresh (first load, symbol change, or manual refresh)
    need_refresh = (
        not st.session_state.vn_stocks_loaded or
        st.session_state.get("last_vn_symbols") != current_vn_symbols or
        st.session_state.get("last_vn_period") != current_vn_period
    )
    
    manual_refresh = st.button("🔄 Refresh Charts", key="refresh_vn")
    
    if manual_refresh or need_refresh:
        # ✅ VALIDATE: Check symbols are not empty
        if not symbols_input or not symbols_input.strip():
            st.error("❌ Please enter at least one stock symbol")
        else:
            try:
                with st.spinner("Loading stock data and generating charts..."):
                    # ✅ CRITICAL FIX: Send as query param, NOT in URL path
                    response = requests.get(
                        f"{API_BASE_URL}/stocks/vn/charts",
                        params={
                            "symbols": symbols_input.strip(),  # ✅ Send as param
                            "period": period
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if not data.get("success"):
                            st.error(f"❌ {data.get('error', 'Unknown error')}")
                            if "message" in data:
                                st.warning(data["message"])
                            st.session_state.vn_chart_data = None
                        else:
                            chart_data = data.get("data", {})
                            
                            if "error" in chart_data:
                                st.error(f"❌ {chart_data['error']}")
                                if "message" in chart_data:
                                    st.info(chart_data["message"])
                                st.session_state.vn_chart_data = None
                            else:
                                # ✅ Store in session state
                                st.session_state.vn_chart_data = chart_data
                                st.session_state.vn_stocks_loaded = True
                                st.session_state.last_vn_symbols = current_vn_symbols
                                st.session_state.last_vn_period = current_vn_period
                    else:
                        st.error(f"API error: {response.status_code}")
                        st.session_state.vn_chart_data = None
                        
            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.vn_chart_data = None
    
    # ✅ Display charts from session state (same as before)
    if st.session_state.get("vn_chart_data"):
        chart_data = st.session_state.vn_chart_data
        
        st.subheader("📊 Stock Statistics")
        
        if "symbols" in chart_data and chart_data["symbols"]:
            cols = st.columns(min(len(chart_data["symbols"]), 4))
            
            for idx, symbol in enumerate(chart_data["symbols"]):
                with cols[idx % 4]:
                    stats = chart_data["stats"][symbol]
                    latest_price = stats['latest_price']
                    
                    if latest_price >= 1000:
                        price_str = f"{latest_price:,.0f} VND"
                    else:
                        price_str = f"{latest_price * 1000:,.0f} VND"
                    
                    st.metric(
                        symbol,
                        price_str,
                        delta=f"{stats['change_percent']:.2f}%"
                    )
                    st.caption(f"Vol: {stats['volume']:,.0f}")
            
            st.divider()
            
            if len(chart_data["symbols"]) > 1 and "comparison" in chart_data.get("charts", {}):
                st.subheader("📈 Price Comparison (Normalized)")
                
                try:
                    fig_json = chart_data['charts']['comparison']
                    fig = go.Figure(json.loads(fig_json))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}")
                
                st.divider()
            
            for symbol in chart_data["symbols"]:
                st.subheader(f"🔍 {symbol} - Detailed Analysis")
                
                tab_candle, tab_tech = st.tabs(["📊 Candlestick", "📈 Technical"])
                
                with tab_candle:
                    if f"{symbol}_candlestick" in chart_data.get("charts", {}):
                        try:
                            fig_json = chart_data['charts'][f'{symbol}_candlestick']
                            fig = go.Figure(json.loads(fig_json))
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                
                with tab_tech:
                    if f"{symbol}_technical" in chart_data.get("charts", {}):
                        try:
                            fig_json = chart_data['charts'][f'{symbol}_technical']
                            fig = go.Figure(json.loads(fig_json))
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                
                st.divider()

# ✅ Tab 4: US Stocks - NO AUTO-LOAD (manual refresh only)
with tab4:
    st.markdown("### 🇺🇸 US Stock Market")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        us_default = "AAPL,MSFT,GOOGL,AMZN"
        us_symbols_input = st.text_input(
            "Enter US stock symbols (comma-separated):",
            us_default,
            help="Example: AAPL,MSFT,TSLA",
            key="us_symbols"
        )
    with col2:
        us_period = st.selectbox("Period:", ["1mo", "3mo", "6mo", "1y"], index=0, key="us_period")
    
    # ✅ CRITICAL: Show warning about EODHD timeout
    st.warning("⚠️ **Note:** US stock data may take 30-60 seconds to load due to EODHD API response time. Click 'Refresh Charts' when ready.")
    
    # ✅ REMOVED: Auto-load staging (no need_refresh_us check)
    # ✅ ONLY: Manual refresh button
    
    if st.button("🔄 Refresh Charts", key="refresh_us", use_container_width=True):
        if not us_symbols_input or not us_symbols_input.strip():
            st.error("❌ Please enter at least one stock symbol")
        else:
            try:
                with st.spinner("⏳ Loading US stock data (this may take up to 60 seconds)..."):
                    # ✅ Show progress
                    progress_text = st.empty()
                    progress_text.text("🌐 Connecting to EODHD API...")
                    
                    response = requests.get(
                        f"{API_BASE_URL}/stocks/us/charts",
                        params={
                            "symbols": us_symbols_input.strip(),
                            "period": us_period
                        },
                        timeout=120  # ✅ CRITICAL: 60→120 seconds timeout
                    )
                    
                    progress_text.text("📊 Processing data...")
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if not data.get("success"):
                            st.error(f"❌ {data.get('error', 'Unknown error')}")
                            if "message" in data:
                                st.warning(data["message"])
                            st.session_state.us_chart_data = None
                        else:
                            chart_data = data.get("data", {})
                            
                            if "error" in chart_data:
                                st.error(f"❌ {chart_data['error']}")
                                if "message" in chart_data:
                                    st.info(chart_data["message"])
                                st.session_state.us_chart_data = None
                            else:
                                st.session_state.us_chart_data = chart_data
                                st.session_state.us_stocks_loaded = True
                                progress_text.text("✅ Data loaded successfully!")
                                time.sleep(1)
                                progress_text.empty()
                    else:
                        st.error(f"API error: {response.status_code}")
                        st.session_state.us_chart_data = None
                        
            except requests.exceptions.Timeout:
                st.error("❌ **Request timeout (120s exceeded).** EODHD API is slow. Try again in a few minutes or use fewer symbols.")
                st.session_state.us_chart_data = None
            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.us_chart_data = None
    
    # ✅ Display charts (same as before)
    if st.session_state.get("us_chart_data"):
        chart_data = st.session_state.us_chart_data
        
        st.subheader("📊 Stock Statistics")
        
        if "symbols" in chart_data and chart_data["symbols"]:
            cols = st.columns(min(len(chart_data["symbols"]), 4))
            
            for idx, symbol in enumerate(chart_data["symbols"]):
                with cols[idx % 4]:
                    stats = chart_data["stats"][symbol]
                    st.metric(
                        symbol,
                        f"${stats['latest_price']:.2f}",
                        delta=f"{stats['change_percent']:.2f}%"
                    )
                    st.caption(f"Vol: {stats['volume']:,.0f}")
            
            st.divider()
            
            if len(chart_data["symbols"]) > 1 and "comparison" in chart_data.get("charts", {}):
                st.subheader("📈 Price Comparison (Normalized)")
                
                try:
                    fig_json = chart_data['charts']['comparison']
                    fig = go.Figure(json.loads(fig_json))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}")
                
                st.divider()
            
            for symbol in chart_data["symbols"]:
                st.subheader(f"🔍 {symbol} - Detailed Analysis")
                
                tab_candle, tab_tech = st.tabs(["📊 Candlestick", "📈 Technical"])
                
                with tab_candle:
                    if f"{symbol}_candlestick" in chart_data.get("charts", {}):
                        try:
                            fig_json = chart_data['charts'][f'{symbol}_candlestick']
                            fig = go.Figure(json.loads(fig_json))
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                
                with tab_tech:
                    if f"{symbol}_technical" in chart_data.get("charts", {}):
                        try:
                            fig_json = chart_data['charts'][f'{symbol}_technical']
                            fig = go.Figure(json.loads(fig_json))
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                
                st.divider()
    else:
        # ✅ Show helpful message
        st.info("💡 **Click 'Refresh Charts' above to load US stock data.** First load may take 30-60 seconds.")
        
        # ✅ Show cache info
        st.markdown("---")
        st.subheader("ℹ️ About US Stock Data")
        
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.markdown("""
            **Data Source:**
            - EODHD API (100k calls/month)
            - End-of-day historical data
            - 24-hour local cache
            """)
        
        with col_info2:
            st.markdown("""
            **Performance:**
            - First load: 30-60 seconds
            - Cached load: <1 second
            - Cache expires: 24 hours
            """)

# Tab 5: News - SIMPLIFIED (no crawl button)
with tab5:
    st.markdown("### 📰 Financial News Search")
    
    # Custom CSS for newspaper-style cards
    st.markdown("""
    <style>
    .news-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: box-shadow 0.3s ease;
    }
    .news-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .news-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 12px;
        line-height: 1.4;
    }
    .news-meta {
        display: flex;
        gap: 20px;
        margin-bottom: 15px;
        font-size: 0.85rem;
        color: #6c757d;
    }
    .news-meta-item {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .news-summary {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #333;
        margin-bottom: 15px;
        border-left: 3px solid #007bff;
        padding-left: 15px;
        background-color: #f1f8ff;
        padding: 12px 15px;
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input(
            "🔍 Search financial news:", 
            placeholder="e.g., gold price, stock market, bitcoin...",
            key="news_search"
        )
    with col2:
        max_results = st.selectbox("Results:", [10, 20, 30], index=0)
    
    if search_query:
        try:
            with st.spinner("Searching news..."):
                response = requests.get(
                    f"{API_BASE_URL}/news/search",
                    params={
                        "query": search_query,
                        "max_results": max_results,
                        "days": 30
                    }
                )
                
                if response.status_code == 200 and response.json().get("success"):
                    data = response.json()
                    articles = data.get("results", [])
                    
                    if not articles:
                        st.warning("No relevant articles found. Try different keywords.")
                    else:
                        st.success(f"✅ Found {len(articles)} articles")
                        st.divider()
                        
                        for idx, article in enumerate(articles):
                            # Parse date
                            try:
                                pub_date = datetime.fromisoformat(article['published_date'].replace('Z', '+00:00'))
                                date_str = pub_date.strftime('%d/%m/%Y')
                                time_str = pub_date.strftime('%H:%M')
                            except:
                                date_str = "N/A"
                                time_str = ""
                            
                            with st.container():
                                # Card HTML
                                st.markdown(f"""
                                <div class="news-card">
                                    <div class="news-title">
                                        {idx+1}. {article['title']}
                                    </div>
                                    <div class="news-meta">
                                        <div class="news-meta-item">
                                            📅 <strong>{date_str}</strong> {time_str}
                                        </div>
                                        <div class="news-meta-item">
                                            📰 <strong>Source:</strong> {article['source']}
                                        </div>
                                    </div>
                                    <div class="news-summary">
                                        {article['snippet']}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # ✅ NEW: 3-column layout for actions
                                col_link, col_summary, col_embed = st.columns([2, 2, 1])
                                
                                with col_link:
                                    st.link_button(
                                        "🔗 Read Full Article", 
                                        article['url'], 
                                        use_container_width=True
                                    )
                                
                                with col_summary:
                                    # ✅ NEW: Show AI summary button
                                    if st.button(f"🤖 AI Summary", key=f"summary_{article['id']}", use_container_width=True):
                                        with st.spinner("Generating summary..."):
                                            try:
                                                # ✅ Call summarization endpoint
                                                summary_response = requests.post(
                                                    f"{API_BASE_URL}/news/article/summarize",
                                                    json={
                                                        "url": article['url'],
                                                        "title": article['title'],
                                                        "content": article.get('full_content', article['snippet'])
                                                    },
                                                    timeout=30
                                                )
                                                
                                                if summary_response.status_code == 200:
                                                    summary_data = summary_response.json()
                                                    
                                                    if summary_data.get("success"):
                                                        # ✅ Show summary in expander
                                                        with st.expander("📄 AI-Generated Summary", expanded=True):
                                                            st.markdown(summary_data.get("summary", ""))
                                                            st.caption(f"Summarized by Gemini AI • {len(summary_data.get('summary', '').split())} words")
                                                    else:
                                                        st.error("Failed to generate summary")
                                                else:
                                                    st.error("Summary service unavailable")
                                            except Exception as e:
                                                st.error(f"Error: {e}")
                                
                                with col_embed:
                                    # ✅ NEW: Manual embed button
                                    if st.button("💾", key=f"embed_{article['id']}", use_container_width=True, help="Add to Knowledge Base"):
                                        with st.spinner("Embedding..."):
                                            try:
                                                embed_response = requests.post(
                                                    f"{API_BASE_URL}/news/article/embed",
                                                    json={
                                                        "url": article['url'],
                                                        "title": article['title'],
                                                        "content": article.get('full_content', article['snippet']),
                                                        "source": article['source'],
                                                        "category": article.get('category', 'general')
                                                    },
                                                    timeout=60
                                                )
                                                
                                                if embed_response.status_code == 200:
                                                    embed_data = embed_response.json()
                                                    if embed_data.get("success"):
                                                        st.success("✅ Added to Knowledge Base!")
                                                    else:
                                                        st.warning(embed_data.get("message", "Already in database"))
                                                else:
                                                    st.error("Failed to embed")
                                            except Exception as e:
                                                st.error(f"Error: {e}")
                                
                                st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.error("Failed to search news")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        # Empty state
        st.info("👆 Enter keywords to search for financial news")
        
        st.markdown("---")
        st.subheader("💡 How it works")
        
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.markdown("""
            **1️⃣ Search**
            - Enter financial keywords
            - Powered by Tavily AI
            - Real-time from trusted sources
            """)
        
        with col_info2:
            st.markdown("""
            **2️⃣ Preview**
            - See article snippets
            - Source & date displayed
            - Sorted by relevance
            """)
        
        with col_info3:
            st.markdown("""
            **3️⃣ Read More**
            - Click link to read full article
            - Opens on original website
            - Get complete information
            """)
        
        # Show cache stats
        st.markdown("---")
        st.subheader("📊 Search Statistics")
        
        try:
            cache_response = requests.get(f"{API_BASE_URL}/news/cache/stats")
            if cache_response.status_code == 200:
                stats = cache_response.json().get("stats", {})
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📦 Cached Articles", stats.get("total_cached", 0))
                with col2:
                    st.metric("💾 Max Capacity", stats.get("max_capacity", 0))
                with col3:
                    st.metric("⏰ TTL (days)", stats.get("ttl_days", 0))
        except:
            pass

# ✅ NEW: Tab 6 - AI Knowledge Base
with tab6:
    st.markdown("### 🧠 AI Knowledge Base")
    st.caption("View what data the AI has learned from")
    
    # Knowledge Stats
    st.subheader("📊 Knowledge Statistics")
    
    try:
        news_response = requests.get(f"{API_BASE_URL}/knowledge/stats")
        
        if news_response.status_code == 200:
            stats = news_response.json()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📰 News Articles", stats.get("news_count", 0))
            with col2:
                st.metric("📈 VN Stock Records", stats.get("vn_stocks_count", 0))
            with col3:
                st.metric("🇺🇸 US Stock Records", stats.get("us_stocks_count", 0))
            with col4:
                st.metric("💰 Gold Price Records", stats.get("gold_count", 0))
            
            # ✅ Show latest gold price
            if stats.get("latest_gold"):
                st.divider()
                st.subheader("💰 Latest Gold Price in Database")
                
                latest = stats["latest_gold"]
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Price", latest.get("latest_price", "N/A"))
                with col2:
                    st.info(f"**Source:** {latest.get('source', 'Unknown')}")
                with col3:
                    st.info(f"**Type:** {latest.get('type', 'Unknown')}")
                
                st.caption(f"Last updated: {latest.get('timestamp', 'N/A')}")
            
            st.divider()
            
            # ✅ NEW: Show recent gold prices
            st.subheader("💰 Recent Gold Price Records")
            
            gold_response = requests.get(f"{API_BASE_URL}/knowledge/recent-gold?limit=10")
            
            if gold_response.status_code == 200:
                gold_data = gold_response.json().get("gold_prices", [])
                
                if gold_data:
                    df_gold = pd.DataFrame(gold_data)
                    df_gold['timestamp'] = pd.to_datetime(df_gold['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    st.dataframe(
                        df_gold[['timestamp', 'type', 'buy_price', 'sell_price', 'source']],
                        column_config={
                            "timestamp": st.column_config.TextColumn("Time", width="small"),
                            "type": st.column_config.TextColumn("Type", width="medium"),
                            "buy_price": st.column_config.NumberColumn("Buy (VND/g)", format="%.0f"),
                            "sell_price": st.column_config.NumberColumn("Sell (VND/g)", format="%.0f"),
                            "source": st.column_config.TextColumn("Source", width="small")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No gold prices recorded yet. Click 'Crawl Gold Prices' to fetch.")
            
            st.divider()
            
            # Recent News in Knowledge Base
            st.subheader("📚 Recent News Articles in Knowledge Base")
            
            recent_response = requests.get(f"{API_BASE_URL}/knowledge/recent-news?limit=20")
            
            if recent_response.status_code == 200:
                recent_news = recent_response.json().get("articles", [])
                
                if recent_news:
                    # Create DataFrame
                    df = pd.DataFrame(recent_news)
                    df['published_time'] = pd.to_datetime(df['published_time']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Display in table
                    st.dataframe(
                        df[['title', 'source', 'published_time']],
                        column_config={
                            "title": st.column_config.TextColumn("Title", width="large"),
                            "source": st.column_config.TextColumn("Source", width="small"),
                            "published_time": st.column_config.TextColumn("Date", width="small")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Show sample content
                    with st.expander("🔍 View Sample Article Content"):
                        sample = recent_news[0]
                        st.markdown(f"**Title:** {sample['title']}")
                        st.markdown(f"**Source:** {sample['source']}")
                        st.markdown(f"**Published:** {sample['published_time']}")
                        st.divider()
                        st.text_area("Content Preview:", sample['content'][:500] + "...", height=200)
                else:
                    st.info("No articles in knowledge base yet. Search for news to populate.")
            else:
                st.error("Failed to load recent news")
            
            # Test RAG Search
            st.divider()
            st.subheader("🧪 Test RAG Search")
            
            test_query = st.text_input("Enter a test query:", placeholder="e.g., What's the latest on gold prices?")
            
            if st.button("🔍 Search Knowledge Base"):
                if test_query:
                    with st.spinner("Searching..."):
                        search_response = requests.get(
                            f"{API_BASE_URL}/knowledge/search",
                            params={"query": test_query, "top_k": 5}
                        )
                        
                        if search_response.status_code == 200:
                            results = search_response.json().get("results", [])
                            
                            if results:
                                st.success(f"Found {len(results)} relevant articles")
                                
                                for idx, result in enumerate(results):
                                    with st.expander(f"Result {idx+1}: {result['title']} (Similarity: {result['similarity']:.2%})"):
                                        st.markdown(f"**Source:** {result['source']}")
                                        st.markdown(f"**Date:** {result['published_time']}")
                                        st.markdown(f"**Content Preview:**")
                                        st.write(result['content'][:300] + "...")
                            else:
                                st.warning("No relevant articles found in knowledge base")
                        else:
                            st.error("Search failed")
        else:
            st.error("Failed to load knowledge statistics")
    except Exception as e:
        st.error(f"Error: {e}")

# Footer
st.divider()
st.caption("💡 Tip: Use the sidebar to update data, then explore visualizations in each tab")