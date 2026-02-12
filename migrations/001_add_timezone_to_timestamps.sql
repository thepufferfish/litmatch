-- Migration: Add timezone support to timestamp columns
-- This converts existing TIMESTAMP columns to TIMESTAMPTZ (TIMESTAMP WITH TIME ZONE)
-- All datetime values will be assumed to be in UTC when converting

-- Update Book.last_scraped column
ALTER TABLE book
ALTER COLUMN last_scraped TYPE TIMESTAMP WITH TIME ZONE
USING last_scraped AT TIME ZONE 'UTC';

-- Update UserRating.created_at and updated_at columns
ALTER TABLE userrating
ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
USING created_at AT TIME ZONE 'UTC';

ALTER TABLE userrating
ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
USING updated_at AT TIME ZONE 'UTC';

-- Update RefreshToken.expires_at and created_at columns
ALTER TABLE refreshtoken
ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE
USING expires_at AT TIME ZONE 'UTC';

ALTER TABLE refreshtoken
ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
USING created_at AT TIME ZONE 'UTC';
