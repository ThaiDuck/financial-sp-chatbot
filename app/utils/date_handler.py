from datetime import datetime, timedelta, date
import logging
import re
import calendar

logger = logging.getLogger(__name__)

class DateContext:
    """Class to provide date context and temporal awareness functions"""
    
    @staticmethod
    def get_current_date():
        """Get current date object - ALWAYS fresh"""
        return datetime.now()
    
    @staticmethod
    def get_all_formats():
        """Get current date in all useful formats - ALWAYS fresh"""
        # Always get a fresh datetime.now()
        now = datetime.now()
        current_year = now.year
        
        # Get month names in Vietnamese
        vn_months = ["tháng 1", "tháng 2", "tháng 3", "tháng 4", "tháng 5", "tháng 6", 
                     "tháng 7", "tháng 8", "tháng 9", "tháng 10", "tháng 11", "tháng 12"]
        
        return {
            "iso": now.strftime('%Y-%m-%d'),
            "dmy": now.strftime('%d/%m/%Y'),
            "mdy": now.strftime('%m/%d/%Y'),
            "full_en": now.strftime('%A, %B %d, %Y'),
            "full_vn": f"{DateContext.get_vietnamese_weekday(now.weekday())}, ngày {now.day} {vn_months[now.month-1]} năm {now.year}",
            "time": now.strftime('%H:%M:%S'),
            "datetime": now.strftime('%Y-%m-%d %H:%M:%S'),
            "day": now.day,
            "month": now.month,
            "year": current_year,  # Explicitly include current year
            "weekday_en": now.strftime('%A'),
            "weekday_vn": DateContext.get_vietnamese_weekday(now.weekday()),
            "month_name_en": now.strftime('%B'),
            "month_name_vn": vn_months[now.month-1],
            "timestamp": int(now.timestamp()),
            "current_year": current_year,  # Add explicit current year
            "current_year_str": str(current_year)  # Add string version
        }
    
    @staticmethod
    def get_vietnamese_weekday(weekday_num):
        """Get Vietnamese weekday name"""
        weekday_names = {
            0: "Thứ hai",
            1: "Thứ ba",
            2: "Thứ tư",
            3: "Thứ năm",
            4: "Thứ sáu",
            5: "Thứ bảy",
            6: "Chủ nhật"
        }
        return weekday_names.get(weekday_num, "")
    
    @staticmethod
    def is_date_query(text):
        """Check if a query is asking for the current date"""
        if not text:
            return False
            
        text = text.lower()
        
        # English date patterns
        english_patterns = [
            "what day is today",
            "what is today's date",
            "what date is today",
            "what is the date today",
            "today's date",
            "current date",
            "what is the current date",
            "what day is it",
            "what date is it"
        ]
        
        # Vietnamese date patterns
        vietnamese_patterns = [
            "hôm nay là ngày mấy",
            "hôm nay là ngày bao nhiêu",
            "ngày hôm nay",
            "ngày bao nhiêu",
            "ngày mấy",
            "hôm nay ngày mấy",
            "bây giờ là ngày mấy"
        ]
        
        # Check for pattern matches
        for pattern in english_patterns + vietnamese_patterns:
            if pattern in text:
                return True
        
        return False
    
    @staticmethod
    def format_date_response(query):
        """Format a response to a date query in the appropriate language - ALWAYS fresh"""
        # Always get fresh date data
        now = datetime.now()
        
        # Get Vietnamese weekday
        weekday_vn = DateContext.get_vietnamese_weekday(now.weekday())
        
        # Format dates
        dmy = now.strftime('%d/%m/%Y')
        full_en = now.strftime('%A, %B %d, %Y')
        
        # Determine language based on the query
        is_vietnamese = any(vn_word in query.lower() for vn_word in 
                        ["ngày", "hôm nay", "mấy", "bao nhiêu", "tháng"])
        
        if is_vietnamese:
            return f"Hôm nay là {weekday_vn}, ngày {dmy}."
        else:
            return f"Today is {full_en}."
    
    @staticmethod
    def get_temporal_context_block():
        """Get a standardized temporal context block for LLM prompts"""
        formats = DateContext.get_all_formats()
        
        return f"""
        [CRITICAL TEMPORAL CONTEXT - ABSOLUTE GROUND TRUTH]
        Today's date: {formats['dmy']} ({formats['iso']})
        Current day: {formats['full_en']}
        Current time: {formats['time']}
        Current year: {formats['current_year']}
        
        THIS IS THE CURRENT DATE AND YEAR. Use this as your reference point for any temporal reasoning.
        You MUST NEVER refer to {formats['current_year']} as a future year - it is the PRESENT year.
        You MUST NEVER claim to lack data after December 2024 or any past date - always provide analysis based on data available as of today.
        """
    
    @staticmethod
    def extract_date_references(text):
        """Extract date references from text for temporal reasoning"""
        text = text.lower()
        now = datetime.now()
        references = {}
        
        # Match common time references
        if "today" in text or "hôm nay" in text:
            references["today"] = now.strftime("%Y-%m-%d")
            
        if "yesterday" in text or "hôm qua" in text:
            yesterday = now - timedelta(days=1)
            references["yesterday"] = yesterday.strftime("%Y-%m-%d")
            
        if "tomorrow" in text or "ngày mai" in text:
            tomorrow = now + timedelta(days=1)
            references["tomorrow"] = tomorrow.strftime("%Y-%m-%d")
            
        if "this week" in text or "tuần này" in text:
            start_of_week = now - timedelta(days=now.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            references["week_start"] = start_of_week.strftime("%Y-%m-%d")
            references["week_end"] = end_of_week.strftime("%Y-%m-%d")
            
        if "this month" in text or "tháng này" in text:
            last_day = calendar.monthrange(now.year, now.month)[1]
            start_of_month = date(now.year, now.month, 1)
            end_of_month = date(now.year, now.month, last_day)
            references["month_start"] = start_of_month.strftime("%Y-%m-%d")
            references["month_end"] = end_of_month.strftime("%Y-%m-%d")
            
        if "this year" in text or "năm nay" in text:
            references["year"] = str(now.year)
        
        return references
