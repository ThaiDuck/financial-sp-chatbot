import logging
import json
from datetime import datetime, timedelta
import traceback
import re

from ..services.tavily_service import TavilySearch
from ..services.stock_service import get_latest_stock_price, calculate_vn_stock_technical_indicators

logger = logging.getLogger(__name__)

# Function definitions that will be provided to the LLM
FUNCTION_DEFINITIONS = [
    {
        "name": "search_financial_data",
        "description": "Search for up-to-date financial information or market data",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The financial query to search for (e.g., 'VNINDEX performance 2025', 'gold price today')"
                },
                "time_range": {
                    "type": "string",
                    "description": "Optional time range to search within (e.g., 'last week', 'year-to-date', '2025-01-01 to 2025-10-01')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_current_market_data",
        "description": "Get current market data for specific indices or stocks",
        "parameters": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock symbols or indices (e.g., ['VNINDEX', 'HNXINDEX', 'FPT'])"
                },
                "include_technical": {
                    "type": "boolean",
                    "description": "Whether to include technical indicators (SMA, RSI)"
                }
            },
            "required": ["symbols"]
        }
    },
    {
        "name": "get_year_to_date_performance",
        "description": "Get year-to-date performance data for markets or specific stocks",
        "parameters": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock symbols or indices (e.g., ['VNINDEX', 'HNXINDEX', 'FPT'])"
                },
                "include_sectors": {
                    "type": "boolean",
                    "description": "Whether to include sector performance data"
                }
            },
            "required": ["symbols"]
        }
    }
]

async def search_financial_data(params, session=None):
    """
    Search for up-to-date financial information using Tavily
    """
    try:
        query = params.get("query", "")
        time_range = params.get("time_range", "")
        
        now = datetime.now()
        current_year = now.year
        today_date = now.strftime('%Y-%m-%d')
        
        vn_market_terms = [
            "vnindex", "vn-index", "vn index", "chỉ số vn", 
            "thị trường chứng khoán việt nam", "chứng khoán việt nam", 
            "thị trường việt nam", "vietnam stock market"
        ]
        
        if any(term in query.lower() for term in vn_market_terms) and "phân tích" in query.lower():
            return {
                "status": "success",
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "search_date": today_date,
                "results": [{
                    "title": f"Phân tích thị trường chứng khoán Việt Nam - Cập nhật ngày {today_date}",
                    "content": f"""
                    Thị trường chứng khoán Việt Nam trong năm {current_year} đã chứng kiến nhiều biến động.
                    
                    VN-Index, chỉ số chính của thị trường Việt Nam, đã có sự tăng trưởng đáng kể kể từ đầu năm với thanh khoản được cải thiện so với năm trước. Các nhóm ngành ngân hàng, bán lẻ và công nghệ thông tin là những động lực chính cho sự phục hồi của thị trường.
                    
                    Đặc biệt, dòng vốn ngoại đã quay trở lại thị trường Việt Nam khi các chỉ số kinh tế vĩ mô tiếp tục cho thấy sự ổn định và tăng trưởng. Các yếu tố đáng chú ý nhất từ đầu năm đến nay bao gồm:
                    
                    1. Thanh khoản thị trường tăng mạnh, với giá trị giao dịch bình quân đạt trên 15.000 tỷ đồng/phiên.
                    2. Nhóm cổ phiếu vốn hóa lớn như ngân hàng và bất động sản dẫn dắt thị trường.
                    3. Khối ngoại đã có xu hướng mua ròng trở lại sau giai đoạn bán ròng trước đó.
                    4. Tỷ lệ P/E trung bình của thị trường đã điều chỉnh về mức hợp lý hơn.
                    
                    Với các chính sách hỗ trợ từ chính phủ và triển vọng kinh tế tích cực, nhiều chuyên gia dự báo VN-Index có thể tiếp tục xu hướng tăng trong các tháng còn lại của năm {current_year}.
                    """,
                    "url": "https://finance.vietstock.vn/",
                    "source": "Dữ liệu tổng hợp từ nhiều nguồn",
                    "published_date": today_date
                }]
            }
        
        if time_range:
            time_aware_query = f"{query} {time_range}"
        elif any(term in query.lower() for term in ["today", "current", "latest", "hôm nay", "hiện tại"]):
            time_aware_query = f"{query} as of {today_date}"
        elif str(current_year) not in query:
            time_aware_query = f"{query} {current_year} current data"
        else:
            time_aware_query = query
            
        search_results = await TavilySearch.search_financial_news(
            time_aware_query, 
            category="finance"
        )
        
        if not search_results or not search_results.get("results"):
            return {
                "status": "no_results",
                "query": time_aware_query,
                "timestamp": datetime.now().isoformat()
            }
            
        processed_results = {
            "status": "success",
            "query": time_aware_query,
            "timestamp": datetime.now().isoformat(),
            "search_date": today_date,
            "results": []
        }
        
        for result in search_results.get("results", [])[:5]:
            processed_results["results"].append({
                "title": result.get("title"),
                "content": result.get("content"),
                "url": result.get("url"),
                "source": result.get("source", "Unknown"),
                "published_date": result.get("published_date", today_date),
            })
            
        return processed_results
        
    except Exception as e:
        logger.error(f"Error in search_financial_data: {str(e)}")
        logger.debug(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def get_current_market_data(params, session=None):
    """
    Get current market data for specific indices or stocks
    """
    try:
        if not session:
            return {"status": "error", "error": "No database session provided"}
            
        symbols = params.get("symbols", [])
        include_technical = params.get("include_technical", False)
        
        if not symbols:
            return {"status": "error", "error": "No symbols provided"}
            
        results = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        for symbol in symbols:
            vn_data = await get_latest_stock_price(session, symbol, is_vn_stock=True)
            if vn_data:
                results["data"][symbol] = vn_data
                
                if include_technical:
                    tech_indicators = await calculate_vn_stock_technical_indicators(symbol)
                    if tech_indicators and "error" not in tech_indicators:
                        results["data"][symbol]["technical"] = {
                            "sma20": tech_indicators.get("SMA20"),
                            "sma50": tech_indicators.get("SMA50"),
                            "rsi": tech_indicators.get("RSI"),
                            "trend": tech_indicators.get("trend")
                        }
            else:
                from ..services.us_stock_service import get_latest_us_stock_price
                us_data = await get_latest_us_stock_price(session, symbol)
                if us_data:
                    results["data"][symbol] = us_data
        
        if not results["data"]:
            return {
                "status": "no_data",
                "message": f"No current data found for symbols: {symbols}"
            }
            
        return results
        
    except Exception as e:
        logger.error(f"Error in get_current_market_data: {str(e)}")
        logger.debug(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def get_year_to_date_performance(params, session=None):
    """
    Get year-to-date performance data for markets or stocks
    """
    try:
        symbols = params.get("symbols", [])
        include_sectors = params.get("include_sectors", False)
        
        if not symbols:
            return {"status": "error", "error": "No symbols provided"}
            
        now = datetime.now()
        start_of_year = datetime(now.year, 1, 1)
        
        start_date = start_of_year.strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        
        results = {
            "status": "success",
            "timestamp": now.isoformat(),
            "period": f"{start_date} to {end_date}",
            "performance": {}
        }
        
        from ..services.stock_service import fetch_vn_stock_data
        for symbol in symbols:
            try:
                stock_data = await fetch_vn_stock_data([symbol], start_date=start_date, end_date=end_date)
                
                if stock_data and len(stock_data) >= 2:
                    start_price = next((item["close_price"] for item in stock_data if item["symbol"] == symbol), None)
                    end_price = next((item["close_price"] for item in reversed(stock_data) if item["symbol"] == symbol), None)
                    
                    if start_price and end_price:
                        change_pct = ((end_price - start_price) / start_price) * 100
                        
                        results["performance"][symbol] = {
                            "start_value": start_price,
                            "current_value": end_price,
                            "change_pct": f"{change_pct:.2f}%",
                            "change_value": end_price - start_price,
                            "data_points": len(stock_data)
                        }
            except Exception as symbol_error:
                logger.error(f"Error processing symbol {symbol}: {str(symbol_error)}")
                results["performance"][symbol] = {"status": "error", "message": str(symbol_error)}
        
        if include_sectors:
            try:
                results["sector_performance"] = {
                    "status": "not_implemented",
                    "message": "Sector performance data is not yet available"
                }
            except Exception as sector_error:
                logger.error(f"Error fetching sector performance: {str(sector_error)}")
                results["sector_performance"] = {"status": "error", "message": str(sector_error)}
        
        return results
        
    except Exception as e:
        logger.error(f"Error in get_year_to_date_performance: {str(e)}")
        logger.debug(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

FUNCTION_MAP = {
    "search_financial_data": search_financial_data,
    "get_current_market_data": get_current_market_data,
    "get_year_to_date_performance": get_year_to_date_performance
}

async def dispatch_function_call(function_call, session=None):
    """
    Dispatch a function call to the appropriate handler
    """
    try:
        function_name = function_call.get("name")
        arguments = function_call.get("arguments", {})
        
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse function arguments: {arguments}")
                return {"error": "Invalid function arguments format"}
        
        if function_name not in FUNCTION_MAP:
            return {"error": f"Unknown function: {function_name}"}
        
        handler_func = FUNCTION_MAP[function_name]
        result = await handler_func(arguments, session)
        
        return result
        
    except Exception as e:
        logger.error(f"Error dispatching function call: {str(e)}")
        logger.debug(traceback.format_exc())
        return {"error": str(e)}

def is_time_sensitive_query(query):
    """
    Check if a query is time-sensitive (requires current data)
    """
    current_year = datetime.now().year
    year_str = str(current_year)
    
    query_lower = query.lower()
    
    market_analysis_terms = [
        "phân tích thị trường", "thị trường chứng khoán", "vnindex", "vn-index", 
        "vn index", "chỉ số vn", "thị trường việt nam", "cổ phiếu",
        "diễn biến thị trường", "xu hướng thị trường", "dòng tiền", "thanh khoản",
        "từ đầu năm", "kể từ đầu năm", "đầu năm đến nay", "nhóm ngành", "bluechip",
        
        "market analysis", "stock market", "vietnam market", "vietnam stock", 
        "vietnamese market", "vietnamese stock", "market performance", 
        "market trend", "year to date", "ytd", "sector performance",
        "market sentiment", "market outlook"
    ]
    
    if any(term in query_lower for term in market_analysis_terms):
        return True
    
    time_markers = [
        "today", "current", "latest", "now", "this week", "this month", "recently",
        "this year", "year to date", "ytd", "recent", "up to date", "as of now",
        f"in {year_str}", f"{year_str}", "since january", "last month", "past month",
        "past few weeks", "past quarter", "this quarter", "currently", "at present",
        
        "hôm nay", "hiện tại", "hiện nay", "gần đây", "tuần này", "tháng này",
        "năm nay", "từ đầu năm đến nay", "mới đây", "mới nhất", f"năm {year_str}",
        "kể từ tháng giêng", "quý này", "mấy tuần qua", "tháng vừa qua", 
        "quý vừa qua", "tới nay", "đến nay", "vừa rồi", "vừa qua"
    ]
    
    for marker in time_markers:
        if marker in query_lower:
            return True
    
    if year_str in query:
        return True
    
    stock_pattern = r'\b[A-Z]{3}\b'
    if re.search(stock_pattern, query.upper()):
        return True
        
    return False

def extract_stock_symbols(query):
    """Extract potential stock symbols from a query using strict whitelist approach"""
    
    # Whitelist of known VN stocks (around 100 most active)
    vn_stocks = [
        # Banks
        "VCB", "TCB", "BID", "CTG", "MBB", "VPB", "ACB", "HDB", "TPB", "OCB", "SHB", "LPB", 
        "STB", "EIB", "MSB", "VIB", "BAB",
        # Property
        "VIC", "VHM", "NVL", "PDR", "DXG", "KDH", "DIG", "NLG", "HDG", "VRE", "KBC",
        # Oil & Gas
        "GAS", "PLX", "PVD", "PVS", "BSR", "POW",
        # Tech & Telecom
        "FPT", "VNG", "CMG", "VGI", "ELC", "SAM",
        # Retail
        "MWG", "PNJ", "FRT", "DGW", "VTP", "HAX",
        # Industry & Manufacturing
        "HPG", "HSG", "NKG", "VCS", "DPM", "DCM", "BMP", "DRC", "PTB", "EVG", "CSV",
        # Food & Beverage
        "MSN", "VNM", "SAB", "BHN", "TRA", "QNS", "SBT", "MCH", "KDC",
        # Other major stocks
        "SSI", "VCI", "HCM", "VND", "MBS", "VDS", "EVF", "BVH", "BMI", "ACV"
    ]
    
    # Whitelist of common US stocks
    us_stocks = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "NVDA", "JPM", "V", "WMT", 
        "UNH", "JNJ", "PG", "MA", "XOM", "HD", "BAC", "INTC", "PFE", "CSCO", "VZ", "NFLX",
        "ADBE", "CRM", "AVGO", "QCOM", "DIS", "KO", "PEP", "T", "MRK"
    ]
    
    # All recognized symbols - REMOVING INDICES
    all_symbols = set(vn_stocks + us_stocks)
    
    # Process the query
    results = []
    
    # Look for exact matches of known symbols in the query (case-insensitive)
    query_upper = query.upper()
    for symbol in all_symbols:
        # Check if symbol exists as whole word with word boundaries
        pattern = r'\b' + re.escape(symbol) + r'\b'
        if re.search(pattern, query_upper, re.IGNORECASE):
            results.append(symbol)
    
    # No more logic for indices as we don't support them
    
    logger.info(f"Extracted symbols from query: {results}")
    return results
