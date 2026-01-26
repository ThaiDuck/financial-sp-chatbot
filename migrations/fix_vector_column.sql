-- This migration will fix issues with the pgvector extension and column types

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Fix vector column in the news table if it exists
DO $$
BEGIN
    -- Check if the table exists
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'news'
    ) THEN
        -- Try to convert existing embedding column to correct vector type
        BEGIN
            -- Attempt to change column type if it's not already vector
            ALTER TABLE news 
            ALTER COLUMN embedding TYPE vector(384)
            USING embedding::vector(384);
            
            RAISE NOTICE 'Successfully updated embedding column to vector type';
            
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Error updating embedding column: %', SQLERRM;
            -- If error, try a more aggressive fix
            BEGIN
                -- Create a backup column
                ALTER TABLE news ADD COLUMN embedding_backup bytea;
                
                -- Try to save any existing data
                UPDATE news SET embedding_backup = embedding::bytea WHERE embedding IS NOT NULL;
                
                -- Drop the problematic column and recreate it
                ALTER TABLE news DROP COLUMN embedding;
                ALTER TABLE news ADD COLUMN embedding vector(384);
                
                RAISE NOTICE 'Recreated embedding column as vector(384)';
            EXCEPTION WHEN others THEN
                RAISE NOTICE 'Could not recreate column: %', SQLERRM;
            END;
        END;
        
        -- Check if the metadata column exists, add it if not
        IF NOT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'news' AND column_name = 'meta_data'
        ) THEN
            ALTER TABLE news ADD COLUMN meta_data TEXT;
            RAISE NOTICE 'Added meta_data column to news table';
        END IF;
        
        -- Create the vector index if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'news_embedding_idx'
        ) THEN
            CREATE INDEX news_embedding_idx 
            ON news 
            USING ivfflat (embedding vector_l2_ops)
            WITH (lists = 100);
            
            RAISE NOTICE 'Created vector index on embedding column';
        END IF;
    END IF;
END $$;
