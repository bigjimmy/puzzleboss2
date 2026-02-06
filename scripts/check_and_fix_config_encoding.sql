-- Check current encoding of config table
SHOW CREATE TABLE config;

-- Check column encoding
SELECT
    COLUMN_NAME,
    CHARACTER_SET_NAME,
    COLLATION_NAME,
    COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'puzzleboss'
  AND TABLE_NAME = 'config';

-- Fix the config table to use utf8mb4
ALTER TABLE config
    CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Verify the change
SELECT
    COLUMN_NAME,
    CHARACTER_SET_NAME,
    COLLATION_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'puzzleboss'
  AND TABLE_NAME = 'config';
