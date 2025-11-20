"""
API diagnostic utilities to test external API connections
"""
import logging
import requests
from datetime import datetime
from ..config import (
    EODHD_API_KEY, EODHD_BASE_URL,
    APISED_API_KEY, APISED_BASE_URL,
    GOLDAPI_KEY,
    TAVILY_API_KEY,
    NEWSDATA_API_KEY,
    NEWSAPI_KEY
)

logger = logging.getLogger(__name__)

def run_all_api_tests():
    """Test all API connections"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test EODHD
    try:
        url = f"{EODHD_BASE_URL}/eod/AAPL.US"
        params = {"api_token": EODHD_API_KEY, "fmt": "json", "limit": 1}
        response = requests.get(url, params=params, timeout=5)
        results["tests"]["eodhd"] = {
            "status": "ok" if response.status_code == 200 else "error",
            "status_code": response.status_code
        }
    except Exception as e:
        results["tests"]["eodhd"] = {"status": "error", "error": str(e)}
    
    # Test Apised Gold
    try:
        url = f"{APISED_BASE_URL}/latest"
        headers = {"x-api-key": APISED_API_KEY}
        params = {"metals": "XAU", "base_currency": "VND", "currencies": "VND"}
        response = requests.get(url, headers=headers, params=params, timeout=5)
        results["tests"]["apised_gold"] = {
            "status": "ok" if response.status_code == 200 else "error",
            "status_code": response.status_code
        }
    except Exception as e:
        results["tests"]["apised_gold"] = {"status": "error", "error": str(e)}
    
    # Test Tavily
    try:
        from tavily import Client
        client = Client(api_key=TAVILY_API_KEY)
        response = client.search("test", max_results=1)
        results["tests"]["tavily"] = {
            "status": "ok" if response else "error"
        }
    except Exception as e:
        results["tests"]["tavily"] = {"status": "error", "error": str(e)}
    
    # Test NewsData.io
    if NEWSDATA_API_KEY:
        try:
            url = f"https://newsdata.io/api/1/archive"
            params = {"apikey": NEWSDATA_API_KEY, "q": "test", "language": "en"}
            response = requests.get(url, params=params, timeout=5)
            results["tests"]["newsdata"] = {
                "status": "ok" if response.status_code == 200 else "error",
                "status_code": response.status_code
            }
        except Exception as e:
            results["tests"]["newsdata"] = {"status": "error", "error": str(e)}
    
    return results
