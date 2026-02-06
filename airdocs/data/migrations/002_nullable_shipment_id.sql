-- Migration: Make documents.shipment_id nullable
-- For registry documents that span multiple shipments

-- SQLite doesn't support ALTER COLUMN, so we need to recreate the table

-- Step 1: Rename old table
ALTER TABLE documents RENAME TO documents_old;

-- Step 2: Create new table with nullable shipment_id
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER,  -- Now nullable for registry documents
    document_type TEXT NOT NULL CHECK(document_type IN ('awb', 'invoice', 'upd', 'invoice_tax', 'act', 'waybill', 'registry_1c')),
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'generated' CHECK(status IN ('generated', 'printed', 'sent', 'archived')),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
);

-- Step 3: Copy data from old table
INSERT INTO documents (id, shipment_id, document_type, file_path, file_name, file_hash, file_size, version, status, generated_at)
SELECT id, shipment_id, document_type, file_path, file_name, file_hash, file_size, version, status, generated_at
FROM documents_old;

-- Step 4: Drop old table
DROP TABLE documents_old;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_documents_shipment ON documents(shipment_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
