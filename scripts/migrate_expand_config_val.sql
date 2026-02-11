-- Expand config.val column to support larger values (like Apps Script code)
-- Current: VARCHAR(8192)
-- New: MEDIUMTEXT (16MB limit)

ALTER TABLE `config` MODIFY COLUMN `val` MEDIUMTEXT DEFAULT NULL;

-- Note: This migration is safe to run multiple times (idempotent)
