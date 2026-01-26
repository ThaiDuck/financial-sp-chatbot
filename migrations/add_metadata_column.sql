-- Add meta_data column to news table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'news' AND column_name = 'meta_data'
    ) THEN
        ALTER TABLE news ADD COLUMN meta_data TEXT;
        RAISE NOTICE 'Added meta_data column to news table';
    ELSE
        RAISE NOTICE 'meta_data column already exists in news table';
    END IF;
END $$;
