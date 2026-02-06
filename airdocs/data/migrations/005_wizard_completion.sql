-- Migration 005: Add wizard completion tracking
ALTER TABLE first_run_info ADD COLUMN wizard_completed INTEGER DEFAULT 0;
ALTER TABLE first_run_info ADD COLUMN wizard_skipped INTEGER DEFAULT 0;

