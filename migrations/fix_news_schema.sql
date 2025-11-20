-- Fix any issues with the news table schema

-- Check if pgvector extension is installed
CREATE EXTENSION IF NOT EXISTS vector;

-- Make sure we have proper transaction handling
BEGIN;

-- 1. Check if embedding column exists, and if not, add it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'news' AND column_name = 'embedding'
    ) THEN
        ALTER TABLE news ADD COLUMN embedding vector(384);
    END IF;
END
$$;

-- 2. Create index on embedding column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE indexname = 'idx_news_embedding'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_news_embedding 
        ON news USING hnsw (embedding vector_cosine_ops) 
        WITH (m = 16, ef_construction = 64);
    END IF;
END
$$;

-- 3. Ensure language column exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'news' AND column_name = 'language'
    ) THEN
        ALTER TABLE news ADD COLUMN language varchar(10) DEFAULT 'en';
    END IF;
END
$$;

-- 4. Add a timestamp column to track when entries were inserted
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'news' AND column_name = 'inserted_at'
    ) THEN
        ALTER TABLE news ADD COLUMN inserted_at timestamp DEFAULT CURRENT_TIMESTAMP;
    END IF;
END
$$;

-- 5. Add GIN index on title and content for text search
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE indexname = 'idx_news_content_search'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_news_content_search 
        ON news USING GIN (to_tsvector('english', title || ' ' || content));
    END IF;
END
$$;

-- 6. Clean up any duplicate URLs to prevent data redundancy
CREATE TEMPORARY TABLE IF NOT EXISTS duplicate_urls AS
    SELECT url, COUNT(*), MAX(published_time) as latest_date
    FROM news
    GROUP BY url
    HAVING COUNT(*) > 1;

DELETE FROM news
WHERE url IN (SELECT url FROM duplicate_urls)
  AND published_time < (SELECT latest_date FROM duplicate_urls WHERE duplicate_urls.url = news.url);

-- 7. Add a UNIQUE constraint on URL if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'news_url_unique'
    ) THEN
        ALTER TABLE news ADD CONSTRAINT news_url_unique UNIQUE (url);
    END IF;
EXCEPTION
    WHEN others THEN
        -- Handle any remaining duplicates before adding constraint
        CREATE TEMPORARY TABLE IF NOT EXISTS remaining_duplicates AS
            SELECT url, COUNT(*), MAX(id) as max_id
            FROM news
            GROUP BY url
            HAVING COUNT(*) > 1;
            
        DELETE FROM news
        WHERE url IN (SELECT url FROM remaining_duplicates)
          AND id < (SELECT max_id FROM remaining_duplicates WHERE remaining_duplicates.url = news.url);
          
        -- Try again
        ALTER TABLE news ADD CONSTRAINT news_url_unique UNIQUE (url);
END
$$;

-- Commit all changes
COMMIT;
