-- Migration 004: first_run_info
-- Table for first run information (singleton)

CREATE TABLE IF NOT EXISTS first_run_info (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Only one record allowed
    first_run_date TIMESTAMP NOT NULL,
    installation_path TEXT NOT NULL,
    data_migration_source TEXT,             -- "data_folder", "appdata_existing", "fresh", "user_choice"
    data_migration_date TIMESTAMP,
    data_migration_success INTEGER DEFAULT 1,
    shortcut_created INTEGER DEFAULT 0,
    portable_mode INTEGER DEFAULT 0,
    initial_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
