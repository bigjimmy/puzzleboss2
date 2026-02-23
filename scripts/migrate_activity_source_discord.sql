-- Migration: Add 'discord' source for puzzcord/Discord bot activity tracking
-- Date: 2026-02-22
-- Safe to re-run (idempotent ALTER TABLE).
--
-- Run with:
--   docker exec puzzleboss-app mysql -u puzzleboss -ppuzzleboss123 puzzleboss < /app/scripts/migrate_activity_source_discord.sql

ALTER TABLE activity
  MODIFY source ENUM('puzzleboss','bigjimmybot','discord') DEFAULT NULL;

INSERT IGNORE INTO config (`key`, `val`) VALUES ('ACTIVITY_SOURCES', 'puzzleboss,bigjimmybot,discord');
