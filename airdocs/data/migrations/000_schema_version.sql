-- Migration 000: Schema Version Table
-- =====================================
-- This table tracks which migrations have been applied

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
