-- Migration: Add new activity types and remove unused sources
-- For existing installs. Safe to re-run (idempotent ALTER TABLE).
--
-- Run with:
--   docker exec puzzleboss-app mysql -u puzzleboss -ppuzzleboss123 puzzleboss < /app/scripts/migrate_activity_types.sql

ALTER TABLE activity
  MODIFY type ENUM('create','revise','comment','interact','solve','change','status','assignment') DEFAULT NULL;

ALTER TABLE activity
  MODIFY source ENUM('puzzleboss','bigjimmybot') DEFAULT NULL;
