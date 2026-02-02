import streamlit as st
import sys
import os
import pandas as pd
import requests
import json
import time
import random
import re
from datetime import datetime, timedelta
from PIL import Image

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import GOOGLE_API_KEY
import google.generativeai as genai

# Import news components
from ui.news_components import (
    load_css, render_news_list, render_news_filters, 
    filter_articles, render_loading_animation
)

# Configure Gemini model
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# App configuration
st.set_page_config(
    page_title="Financial Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS for news display and other components
load_css()

# Initialize session state variables - centralized for consistency
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'tracked_vn_symbols' not in st.session_state:
    st.session_state.tracked_vn_symbols = []

if 'tracked_us_symbols' not in st.session_state:
    st.session_state.tracked_us_symbols = []

if 'news_results' not in st.session_state:
    st.session_state.news_results = []

if 'news_page' not in st.session_state:
    st.session_state.news_page = 1

if 'last_news_query' not in st.session_state:
    st.session_state.last_news_query = ""

# Initialize chart parameters with default values
if 'vn_period' not in st.session_state:
    st.session_state.vn_period = '1mo'

if 'vn_chart_type' not in st.session_state:
    st.session_state.vn_chart_type = 'line'

if 'us_period' not in st.session_state:
    st.session_state.us_period = '1mo'
    
if 'us_chart_type' not in st.session_state:
    st.session_state.us_chart_type = 'line'

# Callback functions that don't rely on widget values as arguments
def update_vn_period():
    st.session_state.vn_period = st.session_state.vn_period_select

def update_vn_chart_type():
    st.session_state.vn_chart_type = st.session_state.vn_chart_type_select
    
def update_us_period():
    st.session_state.us_period = st.session_state.us_period_select

def update_us_chart_type():
    st.session_state.us_chart_type = st.session_state.us_chart_type_select

# Stock Prices Page
def stock_prices_page():
    st.title("Stock Market Data")
    
    # Create tabs for VN and US stock
    vn_tab, us_tab = st.tabs(["Vietnam Market", "US Market"])
    
    # Initialize chart state variables if not present
    if 'vn_period' not in st.session_state:
        st.session_state.vn_period = '1mo'
    if 'vn_chart_type' not in st.session_state:
        st.session_state.vn_chart_type = 'line'
    if 'us_period' not in st.session_state:
        st.session_state.us_period = '1mo'
    if 'us_chart_type' not in st.session_state:
        st.session_state.us_chart_type = 'line'

    with vn_tab:
        # Reset button for tracked symbols
        if st.button("Reset All Tracked Symbols", key="force_reset_symbols"):
            st.session_state.tracked_vn_symbols = []
            st.success("All tracked symbols cleared!")
            st.rerun()
        
        # Input for new symbol
        col1, col2 = st.columns([3, 1])
        with col1:
            new_symbol = st.text_input("Add Symbol", key="vn_symbol_input", 
                                      placeholder="Enter a stock symbol (FPT, VCB, HPG, etc.)")
        with col2:
            if st.button("Add Symbol", key="add_vn_symbol"):
                if new_symbol and new_symbol.upper() not in [s.upper() for s in st.session_state.tracked_vn_symbols]:
                    st.session_state.tracked_vn_symbols.append(new_symbol.upper())
        
        # Add helpful info about stock symbols
        st.info("**Add stock symbols like**: FPT, VCB, HPG, MWG, etc.")
        
        # Display tracked symbols
        if st.session_state.tracked_vn_symbols:
            st.write("Tracked VN Symbols:")
            # Create a container for the symbol chips
            symbol_container = st.container()
            # Display symbols with delete buttons
            cols = symbol_container.columns(min(len(st.session_state.tracked_vn_symbols), 5))
            for i, symbol in enumerate(st.session_state.tracked_vn_symbols):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    if st.button(f"✅ {symbol}", key=f"del_vn_{symbol}", use_container_width=True):
                        st.session_state.tracked_vn_symbols.remove(symbol)
                        st.rerun()
        else:
            st.info("No symbols added yet. Use the input above to add stock symbols.")
        
        # Update button
        if st.session_state.tracked_vn_symbols:
            if st.button("Update VN Stocks", key="update_vn"):
                update_vn_stocks(st.session_state.tracked_vn_symbols)
            
    with us_tab:
        # Input for new symbol
        col1, col2 = st.columns([3, 1])
        with col1:
            new_symbol = st.text_input("Add Symbol", key="us_symbol_input", placeholder="Enter a US stock symbol (AAPL, MSFT, etc.)")
        with col2:
            if st.button("Add Symbol", key="add_us_symbol"):
                if new_symbol and new_symbol.upper() not in [s.upper() for s in st.session_state.tracked_us_symbols]:
                    st.session_state.tracked_us_symbols.append(new_symbol.upper())
        
        # Add helpful info about US stock symbols
        st.info("**Add US stock symbols like**: AAPL, MSFT, AMZN, GOOGL, etc.")
        
        # Display tracked symbols
        if st.session_state.tracked_us_symbols:
            st.write("Tracked US Symbols:")
            # Create a container for the symbol chips
            symbol_container = st.container()
            # Display symbols with delete buttons
            cols = symbol_container.columns(min(len(st.session_state.tracked_us_symbols), 5))
            for i, symbol in enumerate(st.session_state.tracked_us_symbols):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    if st.button(f"✅ {symbol}", key=f"del_us_{symbol}", use_container_width=True):
                        st.session_state.tracked_us_symbols.remove(symbol)
                        st.rerun()
        else:
            st.info("No symbols added yet. Use the input above to add stock symbols.")
        
        # Update button
        if st.session_state.tracked_us_symbols:
            if st.button("Update US Stocks", key="update_us"):
                update_us_stocks(st.session_state.tracked_us_symbols)
        
# Gold Prices Page
def gold_prices_page():
    st.title("Gold Prices in Vietnam")
    # Add Update button
    if st.button("Update Gold Prices", key="update_gold"):
        update_gold_prices()
    # Get latest gold prices
    prices = get_gold_prices()
    if prices:
        for price in prices:
            # Guard label to be non-empty string
            raw_label = price.get("type") or price.get("name") or price.get("gold_type") or price.get("source") or "Gold"
            label = str(raw_label).strip() or "Gold"
            # Prefer a single numeric value, fallback to sell/buy
            val = price.get("price")
            if val is None:
                val = price.get("sell_price") or price.get("buy_price") or 0
            try:
                num_val = float(val)
                display_val = f"{num_val:,.0f} VND"
            except Exception:
                # If not numeric, show as string
                display_val = str(val) if val is not None else "0 VND"
            st.metric(label=label, value=display_val)
    else:
        st.error("Failed to load gold prices. Please try updating.")

# News Search Page - Properly integrated with news components
def news_search_page():
    st.title("Financial News Search")
    
    # Import and properly use the news components
    from ui.news_components import load_css, render_news_list, render_news_filters, filter_articles, normalize_news_article, clean_news_text
    
    # Always load the CSS first
    load_css()
    
    # Initialize session state for news page
    if 'news_page' not in st.session_state:
        st.session_state.news_page = 1
    if 'news_results' not in st.session_state:
        st.session_state.news_results = []
    if 'last_news_query' not in st.session_state:
        st.session_state.last_news_query = ""
        
    # Search form
    with st.form("news_search_form"):
        search_query = st.text_input("Search financial news", 
                                    value=st.session_state.get('last_news_query', ''),
                                    placeholder="Enter keywords to search...")
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("")  # Empty space for alignment
        with col2:
            search_submitted = st.form_submit_button("🔍 Search", use_container_width=True)
    
    # Show filters UI
    filters = render_news_filters()
    
    # If search submitted or we have previous results
    if search_submitted and search_query:
        # Save search query to session state
        st.session_state.last_news_query = search_query
        # Reset to first page when searching
        st.session_state.news_page = 1
        
        # Display loading state
        with st.spinner("Searching for news..."):
            # Search API call
            try:
                response = requests.get(
                    f"{API_BASE_URL}/news/query",
                    params={"query": search_query, "top_k": 20}
                )
                
                if response.status_code == 200:
                    news_results = response.json().get("results", [])
                    
                    # Apply first round of cleaning here
                    cleaned_results = []
                    for article in news_results:
                        if article.get('content'):
                            # Apply aggressive cleaning to remove garbage text
                            article['content'] = clean_news_text(article.get('content', ''))
                            
                            # Only include articles with meaningful content
                            if len(article['content']) > 50:  # Minimum content length
                                cleaned_results.append(article)
                    
                    # Store results in session state
                    st.session_state.news_results = cleaned_results
                else:
                    st.error(f"Error searching news: {response.status_code}")
                    st.session_state.news_results = []
            except Exception as e:
                st.error(f"Error connecting to API: {str(e)}")
                st.session_state.news_results = []
    
    # Apply filters to results if we have them
    if hasattr(st.session_state, 'news_results') and st.session_state.news_results:
        filtered_results = filter_articles(st.session_state.news_results, filters)
        
        if filtered_results:
            # Render news list with proper pagination
            render_news_list(
                filtered_results, 
                page=st.session_state.news_page, 
                items_per_page=5
            )
        else:
            st.info("No articles match your filters. Try adjusting your filter criteria.")
    elif search_submitted:
        st.info("No news articles found matching your search. Try different keywords.")

# Chat Page
def chat_page():
    st.title("Financial Assistant")
    # Reset chat button
    if st.button("Reset Chat"):
        st.session_state.chat_history = []
        st.rerun()
    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    # Chat input
    user_input = st.chat_input("Ask a question about financial markets...")
    if user_input:
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        # Show thinking indicator
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("Thinking...")
            try:
                # Call chat API
                response = requests.post(
                    f"{API_BASE_URL}/chat",
                    json={"messages": st.session_state.chat_history, "stream": False}
                )
                if response.status_code == 200:
                    result = response.json()
                    assistant_response = result.get("response", "Sorry, I couldn't generate a response.")
                    # Update placeholder with response
                    message_placeholder.markdown(assistant_response)
                    # Add assistant message to chat history
                    st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
                else:
                    message_placeholder.markdown(f"Error: {response.status_code}. Please try again.")
            except Exception as e:
                message_placeholder.markdown(f"Error connecting to API: {str(e)}. Please try again.")

# API functions
def update_vn_stocks(symbols):
    try:
        response = requests.get(f"{API_BASE_URL}/stock/vn/update", params={"symbols": symbols})
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                st.success(f"Updated {data.get('count')} stock records.")
                display_vn_stock_data(symbols)
            else:
                st.error("Failed to update stock data.")
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def update_us_stocks(symbols):
    try:
        response = requests.get(f"{API_BASE_URL}/stock/us/update", params={"symbols": symbols})
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                st.success(f"Updated {data.get('count')} stock records.")
                display_us_stock_data(symbols)
            else:
                st.error("Failed to update stock data.")
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def display_vn_stock_data(symbols):
    try:
        # Create tabs
        price_tab, chart_tab = st.tabs(["Price Data", "Charts"])
        with price_tab:
            # Get and display price data for each symbol
            for symbol in symbols:
                try:
                    response = requests.get(f"{API_BASE_URL}/stock/vn/{symbol}")
                    if response.status_code == 200:
                        data = response.json().get("price")
                        if data:
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                st.metric(label=f"{symbol}", value=f"{data['close_price']:,.2f}")
                            with col2:
                                st.text(f"Open: {data['open_price']:,.2f} | High: {data['high']:,.2f} | Low: {data['low']:,.2f}")
                                st.text(f"Volume: {data['volume']:,.0f} | Date: {data['timestamp']}")
                        else:
                            st.error(f"No data available for {symbol}")
                    else:
                        st.error(f"Error retrieving data for {symbol}: {response.status_code}")
                except Exception as e:
                    st.error(f"Error processing {symbol}: {str(e)}")
        with chart_tab:
            # Time period selection
            period_options = ["1w", "1mo", "3mo", "6mo", "1y", "max"]
            period_labels = {
                "1w": "1 Week", "1mo": "1 Month", "3mo": "3 Months",
                "6mo": "6 Months", "1y": "1 Year", "max": "Maximum"
            }
            col1, col2 = st.columns([3, 2])
            with col1:
                selected_period = st.selectbox(
                    "Select time period", 
                    options=period_options,
                    format_func=lambda x: period_labels.get(x, x),
                    index=period_options.index(st.session_state.vn_period),
                    key="vn_period_select"
                )
                # Update session state directly after selection
                st.session_state.vn_period = selected_period
            with col2:
                selected_chart_type = st.radio(
                    "Chart type", 
                    options=["line", "candle"],
                    index=0 if st.session_state.vn_chart_type == "line" else 1,
                    horizontal=True, 
                    key="vn_chart_type_select"
                )
                # Update session state directly after selection
                st.session_state.vn_chart_type = selected_chart_type
            ind_tab, comp_tab = st.tabs(["Individual Charts", "Comparison"])
            with ind_tab:
                for symbol in symbols:
                    try:
                        st.subheader(f"{symbol} Chart")
                        response = requests.get(
                            f"{API_BASE_URL}/stock/vn/{symbol}/chart",
                            params={
                                "period": st.session_state.vn_period, 
                                "chart_type": st.session_state.vn_chart_type
                            }
                        )
                        if response.status_code == 200:
                            chart_data = response.json()
                            if chart_data.get("chart"):
                                st.image(f"data:image/png;base64,{chart_data['chart']}")
                            else:
                                st.error(f"No chart data for {symbol}")
                        else:
                            st.error(f"Error fetching chart for {symbol}: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error rendering chart for {symbol}: {str(e)}")
            with comp_tab:
                if len(symbols) > 1:
                    try:
                        st.subheader("Comparison Chart")
                        response = requests.get(
                            f"{API_BASE_URL}/stock/compare",
                            params={
                                "symbols": symbols, 
                                "period": st.session_state.vn_period, 
                                "is_vn_stock": True
                            }
                        )
                        if response.status_code == 200:
                            chart_data = response.json()
                            if chart_data.get("chart"):
                                st.image(f"data:image/png;base64,{chart_data['chart']}")
                            else:
                                st.error("Failed to generate comparison chart")
                        else:
                            st.error(f"Error fetching comparison chart: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error rendering comparison chart: {str(e)}")
                else:
                    st.info("Add more symbols to compare.")
    except Exception as e:
        st.error(f"Error displaying stock data: {str(e)}")

def display_us_stock_data(symbols):
    try:
        # Create tabs
        price_tab, chart_tab, extra_tab = st.tabs(["Price Data", "Charts", "Additional Info"])
        with price_tab:
            # Get and display price data for each symbol
            for symbol in symbols:
                try:
                    response = requests.get(f"{API_BASE_URL}/stock/us/{symbol}")
                    if response.status_code == 200:
                        data = response.json().get("price")
                        if data:
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                st.metric(label=f"{symbol}", value=f"${data['close_price']:,.2f}")
                            with col2:
                                st.text(f"Open: ${data['open_price']:,.2f} | High: ${data['high']:,.2f} | Low: ${data['low']:,.2f}")
                                st.text(f"Volume: {data['volume']:,.0f} | Date: {data['timestamp']}")
                        else:
                            st.error(f"No data available for {symbol}")
                    else:
                        st.error(f"Error retrieving data for {symbol}: {response.status_code}")
                except Exception as e:
                    st.error(f"Error processing {symbol}: {str(e)}")
        with chart_tab:
            # Time period selection
            period_options = ["1w", "1mo", "3mo", "6mo", "1y", "max"]
            period_labels = {
                "1w": "1 Week", "1mo": "1 Month", "3mo": "3 Months",
                "6mo": "6 Months", "1y": "1 Year", "max": "Maximum"
            }
            col1, col2 = st.columns([3, 2])
            with col1:
                selected_period = st.selectbox(
                    "Select time period", 
                    options=period_options,
                    format_func=lambda x: period_labels.get(x, x),
                    index=period_options.index(st.session_state.us_period),
                    key="us_period_select"
                )
                # Update session state directly after selection
                st.session_state.us_period = selected_period
            with col2:
                selected_chart_type = st.radio(
                    "Chart type", 
                    options=["line", "candle"],
                    index=0 if st.session_state.us_chart_type == "line" else 1,
                    horizontal=True, 
                    key="us_chart_type_select"
                )
                # Update session state directly after selection
                st.session_state.us_chart_type = selected_chart_type
            ind_tab, comp_tab = st.tabs(["Individual Charts", "Comparison"])
            with ind_tab:
                for symbol in symbols:
                    try:
                        st.subheader(f"{symbol} Chart")
                        response = requests.get(
                            f"{API_BASE_URL}/stock/us/{symbol}/chart",
                            params={
                                "period": st.session_state.us_period, 
                                "chart_type": st.session_state.us_chart_type
                            }
                        )
                        if response.status_code == 200:
                            chart_data = response.json()
                            if chart_data.get("chart"):
                                st.image(f"data:image/png;base64,{chart_data['chart']}")
                            else:
                                st.error(f"No chart data for {symbol}")
                        else:
                            st.error(f"Error fetching chart for {symbol}: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error rendering chart for {symbol}: {str(e)}")
            with comp_tab:
                if len(symbols) > 1:
                    try:
                        st.subheader("Comparison Chart")
                        response = requests.get(
                            f"{API_BASE_URL}/stock/compare",
                            params={
                                "symbols": symbols, 
                                "period": st.session_state.us_period, 
                                "is_vn_stock": False
                            }
                        )
                        if response.status_code == 200:
                            chart_data = response.json()
                            if chart_data.get("chart"):
                                st.image(f"data:image/png;base64,{chart_data['chart']}")
                            else:
                                st.error("Failed to generate comparison chart")
                        else:
                            st.error(f"Error fetching comparison chart: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error rendering comparison chart: {str(e)}")
                else:
                    st.info("Add more symbols to compare.")
        with extra_tab:
            # Display additional information
            for symbol in symbols:
                try:
                    st.subheader(f"{symbol} Information")
                    # Get company profile
                    profile_response = requests.get(f"{API_BASE_URL}/stock/us/{symbol}/profile")
                    if profile_response.status_code == 200:
                        profile = profile_response.json().get("profile")
                        if profile:
                            st.write("**Company Profile**")
                            st.write(f"**Name:** {profile.get('name', 'N/A')}")
                            st.write(f"**Industry:** {profile.get('industry', 'N/A')}")
                            st.write(f"**Sector:** {profile.get('sector', 'N/A')}")
                            st.write(f"**Description:** {profile.get('description', 'N/A')}")
                        else:
                            st.info(f"No profile information for {symbol}")
                    # Get peers
                    peers_response = requests.get(f"{API_BASE_URL}/stock/us/{symbol}/peers")
                    if peers_response.status_code == 200:
                        peers = peers_response.json().get("peers")
                        if peers and len(peers) > 0:
                            st.write("**Similar Companies:**")
                            st.write(", ".join(peers))
                        else:
                            st.info(f"No peer information for {symbol}")
                except Exception as e:
                    st.error(f"Error fetching additional info for {symbol}: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying stock data: {str(e)}")

def update_gold_prices():
    try:
        response = requests.get(f"{API_BASE_URL}/gold/update")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                st.success(f"Updated {data.get('count')} gold price records.")
            else:
                st.error("Failed to update gold prices.")
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def get_gold_prices():
    try:
        response = requests.get(f"{API_BASE_URL}/gold/latest")
        if response.status_code == 200:
            return response.json().get("prices", [])
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

# Main app - clean, consistent navigation
def main():
    # Application title and sidebar
    st.sidebar.title("Financial Assistant")
    st.sidebar.image("https://raw.githubusercontent.com/zdyourdream/public_images/main/finance_robot_64.png", width=64)
    # Sidebar navigation
    page = st.sidebar.radio("Navigate", 
                          ["Chat", "Gold Prices", "Stock Prices", "News Search"])
    if page == "Chat":
        chat_page()
    elif page == "Gold Prices":
        gold_prices_page()
    elif page == "Stock Prices":
        stock_prices_page()
    elif page == "News Search":
        news_search_page()
    # Show API status in sidebar
    with st.sidebar.expander("API Status"):
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                status = response.json()
                st.success(f"API Status: {status.get('status', 'OK')}")
                st.text(f"DB Status: {status.get('db_status', 'Unknown')}")
                # System stats
                if "system" in status:
                    system = status["system"]
                    st.progress(system.get("cpu_percent", 0) / 100, "CPU")
                    st.progress(system.get("memory", {}).get("percent_used", 0) / 100, "Memory")
                    st.progress(system.get("disk", {}).get("percent_used", 0) / 100, "Disk")
            else:
                st.error(f"API Status: Error {response.status_code}")
        except Exception as e:
            st.error(f"API Status: Connection Error ({str(e)})")

if __name__ == "__main__":
    main()
