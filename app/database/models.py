from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime

Base = declarative_base()

class GoldPrice(Base):
    __tablename__ = "gold_prices"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(20)) 
    type = Column(String(50))    
    location = Column(String(50))
    buy_price = Column(Float)
    sell_price = Column(Float)
    timestamp = Column(DateTime, default=datetime.now)
    
    __table_args__ = (
        Index('idx_gold_timestamp', timestamp.desc()),
    )

class VNStock(Base):
    __tablename__ = "vn_stocks"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    open_price = Column(Float)
    close_price = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime)
    
    __table_args__ = (
        Index('idx_vn_stocks_symbol', symbol),
        Index('idx_vn_stocks_timestamp', timestamp.desc()),
    )

class USStock(Base):
    __tablename__ = "us_stocks"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    open_price = Column(Float)
    close_price = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime)
    
    __table_args__ = (
        Index('idx_us_stocks_symbol', symbol),
        Index('idx_us_stocks_timestamp', timestamp.desc()),
    )

class NewsArticle(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500))  
    content = Column(Text)
    source = Column(String(100))
    url = Column(String(1000), unique=True, index=True) 
    published_time = Column(DateTime, index=True)
    language = Column(String(5), default='en')
    embedding = Column(Vector(384), nullable=True)
    meta_data = Column(Text, nullable=True) 
    
    __table_args__ = (
        Index('idx_news_published', published_time.desc()),
        Index('idx_news_source', source),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
