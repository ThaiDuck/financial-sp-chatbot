import logging
from typing import List, Dict, Any
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from sqlalchemy.orm import Session
import json
from datetime import datetime
import re

from .tools import create_db_tools
from ..prompts import (
    SYSTEM_PROMPT,
    ROUTER_PROMPT,
    NEWS_PROMPT,
    GOLD_PROMPT,
    STOCK_PROMPT,
    DEFAULT_PROMPT
)
from ..config import GOOGLE_API_KEY
from ..utils.function_calling import (
    FUNCTION_DEFINITIONS,
    dispatch_function_call,
    is_time_sensitive_query
)

logger = logging.getLogger(__name__)

def get_llm():
    """Initialize LLM with optimal token limits"""
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 2048,
    }

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.3,
        max_tokens=2048,
        safety_settings=safety_settings,
        generation_config=generation_config,
        system_instruction=SYSTEM_PROMPT,
        convert_system_message_to_human=True,
    )

def create_intent_router(llm):
    """Create intent router"""
    router_prompt = PromptTemplate(
        template=ROUTER_PROMPT,
        input_variables=["input"],
    )
    
    router_chain = LLMChain(llm=llm, prompt=router_prompt, verbose=False)
    
    def parse_router_output(output):
        if isinstance(output, dict):
            clean_output = output.get("text", output.get("response", str(output))).strip().lower()
        else:
            clean_output = str(output).strip().lower()
        
        for dest in ["gold", "stock", "news", "default"]:
            if dest in clean_output:
                return {"destination": dest}
        
        return {"destination": "default"}
    
    from langchain.schema.runnable import RunnableLambda
    return router_chain | RunnableLambda(parse_router_output)

def create_chat_chain(session: Session):
    """Create chat chain"""
    tools = create_db_tools(session)
    llm = get_llm()
    intent_router = create_intent_router(llm)
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    gold_prompt = PromptTemplate(
        template=GOLD_PROMPT,
        input_variables=["gold_data", "query", "today_date"]
    )
    gold_chain = LLMChain(llm=llm, prompt=gold_prompt, verbose=False)
    
    stock_prompt = PromptTemplate(
        template=STOCK_PROMPT,
        input_variables=["stock_data", "query", "today_date"]
    )
    stock_chain = LLMChain(llm=llm, prompt=stock_prompt, verbose=False)
    
    news_prompt = PromptTemplate(
        template=NEWS_PROMPT,
        input_variables=["context", "query", "today_date"]
    )
    news_chain = LLMChain(llm=llm, prompt=news_prompt, verbose=False)
    
    default_prompt = PromptTemplate(
        template=DEFAULT_PROMPT,
        input_variables=["input", "today_date"]
    )
    default_chain = LLMChain(llm=llm, prompt=default_prompt, verbose=False)
    
    return {
        "tools": tools,
        "llm": llm,
        "intent_router": intent_router,
        "news_chain": news_chain,
        "gold_chain": gold_chain,
        "stock_chain": stock_chain,
        "default_chain": default_chain,
        "session": session
    }

def _detect_language(text: str) -> str:
    """
    Detect if text is Vietnamese or English
    """
    vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
    
    for char in text.lower():
        if char in vietnamese_chars:
            return "vietnamese"
    
    return "english"

async def route_to_gold_chain(query, gold_chain, tools, session):
    """✅ FIXED: Force language matching"""
    try:
        gold_tool = [tool for tool in tools if tool.name == "gold_prices"][0]
        
        gold_data_raw = gold_tool.func()
        
        if isinstance(gold_data_raw, list) and len(gold_data_raw) > 0:
            # Take only first 2 gold types
            essential_data = []
            
            for item in gold_data_raw[:2]:
                essential_data.append(
                    f"{item.get('type')}: Mua {item.get('buy_price', 0):,.0f} - "
                    f"Bán {item.get('sell_price', 0):,.0f} VND/g"
                )
            
            gold_context = "\n".join(essential_data)
        else:
            gold_context = str(gold_data_raw)[:200]
        
        # ✅ CRITICAL: Detect language and inject into prompt
        lang = _detect_language(query)
        
        if lang == "vietnamese":
            # Force Vietnamese instruction
            enhanced_query = f"[TRẢ LỜI BẰNG TIẾNG VIỆT] {query}"
        else:
            enhanced_query = f"[REPLY IN ENGLISH] {query}"
        
        today_date = datetime.now().strftime('%Y-%m-%d')
        return gold_chain.run(gold_data=gold_context, query=enhanced_query, today_date=today_date)
        
    except Exception as e:
        logger.error(f"Error in gold chain: {e}")
        return "Xin lỗi, không thể truy xuất thông tin giá vàng lúc này."

async def route_to_stock_chain(query, stock_chain, tools, session):
    """✅ FIXED: Force language matching"""
    try:
        from ..utils.function_calling import extract_stock_symbols
        symbols = extract_stock_symbols(query)
        
        if symbols:
            from ..database.models import VNStock, USStock
            from datetime import timedelta
            
            cutoff = datetime.now() - timedelta(days=7)
            stock_data_text = []
            found_in_db = False
            
            symbols = symbols[:3]
            
            # Check VN stocks
            vn_symbols = [s for s in symbols if len(s) == 3]
            for symbol in vn_symbols:
                records = session.query(VNStock)\
                    .filter(VNStock.symbol == symbol)\
                    .filter(VNStock.timestamp >= cutoff)\
                    .order_by(VNStock.timestamp.desc())\
                    .limit(7)\
                    .all()
                
                if records:
                    found_in_db = True
                    latest = records[0]
                    oldest = records[-1]
                    change = ((latest.close_price - oldest.close_price) / oldest.close_price) * 100
                    
                    high_7d = max(r.high for r in records)
                    low_7d = min(r.low for r in records)
                    
                    # ✅ VALIDATION: Ensure prices are valid
                    actual_price = latest.close_price * 1000
                    actual_high = high_7d * 1000
                    actual_low = low_7d * 1000
                    
                    if actual_price <= 0 or actual_high <= 0 or actual_low <= 0:
                        logger.warning(f"⚠️ Invalid price data for {symbol}, skipping")
                        continue
                    
                    # ✅ CLEAR FORMAT for LLM
                    stock_data_text.append(
                        f"Stock: {symbol} (Vietnamese market)\n"
                        f"Current Price: {actual_price:,.0f} VND\n"
                        f"7-Day Change: {change:+.2f}%\n"
                        f"7-Day High: {actual_high:,.0f} VND\n"
                        f"7-Day Low: {actual_low:,.0f} VND\n"
                        f"Source: Database (Last 7 days real data)\n"
                        f"Note: These are EXACT prices from our database. Use them AS-IS."
                    )
            
            # Check US stocks
            us_symbols = [s for s in symbols if len(s) >= 4]
            for symbol in us_symbols:
                records = session.query(USStock)\
                    .filter(USStock.symbol == symbol)\
                    .filter(USStock.timestamp >= cutoff)\
                    .order_by(USStock.timestamp.desc())\
                    .limit(7)\
                    .all()
                
                if records:
                    found_in_db = True
                    latest = records[0]
                    oldest = records[-1]
                    change = ((latest.close_price - oldest.close_price) / oldest.close_price) * 100
                    
                    high_7d = max(r.high for r in records)
                    low_7d = min(r.low for r in records)
                    
                    # ✅ VALIDATION
                    if latest.close_price <= 0:
                        logger.warning(f"⚠️ Invalid price for {symbol}, skipping")
                        continue
                    
                    stock_data_text.append(
                        f"Stock: {symbol} (US market)\n"
                        f"Current Price: ${latest.close_price:.2f}\n"
                        f"7-Day Change: {change:+.2f}%\n"
                        f"7-Day High: ${high_7d:.2f}\n"
                        f"7-Day Low: ${low_7d:.2f}\n"
                        f"Source: Database (Last 7 days real data)\n"
                        f"Note: These are EXACT prices from our database. Use them AS-IS."
                    )
            
            if found_in_db:
                logger.info(f"✅ Using DB data for stocks: {symbols}")
                today_date = datetime.now().strftime('%Y-%m-%d')
                
                full_context = "\n\n".join(stock_data_text)
                
                # ✅ Force language
                lang = _detect_language(query)
                if lang == "vietnamese":
                    enhanced_query = f"[TRẢ LỜI BẰNG TIẾNG VIỆT] {query}"
                else:
                    enhanced_query = f"[REPLY IN ENGLISH] {query}"
                
                # ✅ LOG what we're sending to LLM
                logger.info(f"📊 Sending to LLM:\n{full_context[:500]}...")
                
                response = stock_chain.run(
                    stock_data=full_context, 
                    query=enhanced_query,  # ✅ Use enhanced query
                    today_date=today_date
                )
                
                # ✅ VALIDATE response doesn't contain hallucinations
                # Check if response contains the actual price from data
                for line in stock_data_text:
                    if "VND" in line and "Current Price:" in line:
                        # Extract expected price
                        import re
                        match = re.search(r'Current Price: ([\d,]+) VND', line)
                        if match:
                            expected_price = match.group(1)
                            if expected_price not in response:
                                logger.warning(f"⚠️ LLM response may not use exact data! Expected: {expected_price}")
                
                return response
        
        # Fallback
        logger.warning(f"⚠️ No DB data for query")
        today_date = datetime.now().strftime('%Y-%m-%d')
        return stock_chain.run(
            stock_data="Data Status: No data available in database.\nPlease ask user to specify stock symbol (e.g., VCB for Vietnam, AAPL for US).", 
            query=query, 
            today_date=today_date
        )
        
    except Exception as e:
        logger.error(f"Error in stock chain: {e}")
        return "Xin lỗi, không thể truy xuất thông tin cổ phiếu."

async def route_to_news_chain(query, news_chain, session):
    """✅ FIXED: Force language matching"""
    try:
        from ..services.news_service import semantic_search
        
        # ✅ Reduce from 5 to 3 articles
        docs = await semantic_search(session=session, query=query, top_k=3)
        
        # ✅ CRITICAL: Detect language
        lang = _detect_language(query)
        
        if docs and len(docs) > 0:
            # ✅ TRUNCATE: Only 150 chars per article
            context = "\n\n".join([
                f"[{i+1}] {doc['title']}\n{doc['content'][:150]}..."
                for i, doc in enumerate(docs)
            ])
            
            # ✅ Force language
            if lang == "vietnamese":
                enhanced_query = f"[TRẢ LỜI BẰNG TIẾNG VIỆT] {query}"
            else:
                enhanced_query = f"[REPLY IN ENGLISH] {query}"
            
            today_date = datetime.now().strftime('%Y-%m-%d')
            response = news_chain.run(context=context, query=enhanced_query, today_date=today_date)
            
            logger.info(f"✅ Answered from RAG DB ({len(docs)} articles)")
            return response
        
        # Tavily fallback
        logger.warning("⚠️ No RAG data, falling back to Tavily")
        
        from ..utils.function_calling import search_financial_data
        
        search_results = await search_financial_data(
            {"query": query},
            session=session
        )
        
        if search_results and search_results.get("status") == "success":
            # ✅ TRUNCATE: Max 2 results, 200 chars each
            context = "\n\n".join([
                f"[{i+1}] {result['title']}\n{result['content'][:200]}"
                for i, result in enumerate(search_results.get("results", [])[:2])
            ])
            
            # ✅ Force language
            if lang == "vietnamese":
                enhanced_query = f"[TRẢ LỜI BẰNG TIẾNG VIỆT] {query}"
            else:
                enhanced_query = f"[REPLY IN ENGLISH] {query}"
            
            today_date = datetime.now().strftime('%Y-%m-%d')
            response = news_chain.run(context=context, query=enhanced_query, today_date=today_date)
            
            logger.info("✅ Answered using Tavily backup")
            return response
        
        return "Không tìm thấy tin tức liên quan."
        
    except Exception as e:
        logger.error(f"Error in news chain: {e}")
        return "Xin lỗi, không thể truy xuất tin tức."

async def process_user_query(chain_dict, user_message, conversation_history=None):
    """✅ OPTIMIZED: Reduce conversation context"""
    try:
        # ✅ REDUCED: From 4 to 2 messages (1 turn)
        if conversation_history and len(conversation_history) > 0:
            context_messages = conversation_history[-2:]  # ✅ Only last turn
            
            if len(context_messages) > 1:
                # ✅ COMPACT: One-line context
                last_user = context_messages[-2]['content'] if len(context_messages) >= 2 else ""
                last_bot = context_messages[-1]['content'][:100] if len(context_messages) >= 1 else ""
                
                contextual_query = f"[Trước: {last_user[:50]}... Bot: {last_bot}...]\n\n{user_message}"
                
                logger.info(f"Using minimal context (1 turn)")
            else:
                contextual_query = user_message
        else:
            contextual_query = user_message
        
        # Route based on intent
        intent_router = chain_dict.get("intent_router")
        result = intent_router.invoke({"input": contextual_query})
        destination = result.get("destination", "default")
        
        logger.info(f"🎯 Routing to: {destination}")
        
        # Route to appropriate chain
        if destination == "gold":
            return await route_to_gold_chain(contextual_query, chain_dict["gold_chain"], chain_dict["tools"], chain_dict["session"])
        elif destination == "stock":
            return await route_to_stock_chain(contextual_query, chain_dict["stock_chain"], chain_dict["tools"], chain_dict["session"])
        elif destination == "news":
            return await route_to_news_chain(contextual_query, chain_dict["news_chain"], chain_dict["session"])
        else:
            today_date = datetime.now().strftime('%Y-%m-%d')
            return chain_dict["default_chain"].run(input=contextual_query, today_date=today_date)
            
    except Exception as e:
        logger.error(f"❌ Error processing query: {e}")
        return "Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi."