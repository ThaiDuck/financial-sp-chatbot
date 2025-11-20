-- Migration script to update the news table schema

-- First check if pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Check if the embedding column exists, and add it if not
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

-- Create index on embedding column for faster similarity searches
CREATE INDEX IF NOT EXISTS idx_news_embedding ON news USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Run this script with:
-- psql -U postgres -d finance_bot -f migrations/update_news_schema.sql
