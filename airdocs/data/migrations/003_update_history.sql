-- Migration 003: update_history
-- Table for tracking update history

CREATE TABLE IF NOT EXISTS update_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    previous_version TEXT,
    channel TEXT NOT NULL,              -- "latest" or "stable"
    install_method TEXT NOT NULL,       -- "auto" or "manual"
    download_size INTEGER,              -- size in bytes
    download_duration INTEGER,          -- seconds
    install_success INTEGER NOT NULL,   -- 1 = success, 0 = failure
    error_message TEXT,
    rollback_occurred INTEGER DEFAULT 0,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_update_history_version ON update_history(version);
CREATE INDEX idx_update_history_date ON update_history(installed_at);
