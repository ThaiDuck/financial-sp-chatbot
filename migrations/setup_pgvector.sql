-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Set up all tables if they don't exist
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,
    source VARCHAR(100),
    url VARCHAR(512),
    published_time TIMESTAMP,
    language VARCHAR(5) DEFAULT 'en',
    embedding VECTOR(384),
    meta_data TEXT  -- Changed from metadata to meta_data
);

CREATE TABLE IF NOT EXISTS gold_prices (
    id SERIAL PRIMARY KEY,
    source VARCHAR(20),
    type VARCHAR(50),
    location VARCHAR(50),
    buy_price FLOAT,
    sell_price FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vn_stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    open_price FLOAT,
    close_price FLOAT,
    high FLOAT,
    low FLOAT,
    volume FLOAT,
    timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS us_stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    open_price FLOAT,
    close_price FLOAT,
    high FLOAT,
    low FLOAT,
    volume FLOAT,
    timestamp TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_news_published ON news (published_time DESC);
CREATE INDEX IF NOT EXISTS idx_news_source ON news (source);
CREATE INDEX IF NOT EXISTS idx_gold_timestamp ON gold_prices (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_vn_stocks_symbol ON vn_stocks (symbol);
CREATE INDEX IF NOT EXISTS idx_vn_stocks_timestamp ON vn_stocks (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_us_stocks_symbol ON us_stocks (symbol);
CREATE INDEX IF NOT EXISTS idx_us_stocks_timestamp ON us_stocks (timestamp DESC);

-- Create vector index if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'news_embedding_idx') THEN
        CREATE INDEX news_embedding_idx ON news USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
        RAISE NOTICE 'Created vector index on embedding column';
    END IF;
END $$;

-- Create a function to convert array to vector for migrations
CREATE OR REPLACE FUNCTION array_to_vector(arr float[]) RETURNS vector AS $$
BEGIN
    RETURN arr::vector;
END;
$$ LANGUAGE plpgsql;
