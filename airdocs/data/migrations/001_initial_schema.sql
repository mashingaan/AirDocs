-- Migration 001: Initial Schema
-- ==============================
-- Creates all base tables for AWB Dispatcher

-- ==========================================
-- PARTIES (Контрагенты)
-- ==========================================
CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    party_type TEXT NOT NULL CHECK(party_type IN ('shipper', 'consignee', 'agent', 'carrier')),
    name TEXT NOT NULL,
    address TEXT,
    inn TEXT,
    kpp TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);
CREATE INDEX IF NOT EXISTS idx_parties_inn ON parties(inn);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type);
CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(is_active);

-- ==========================================
-- TEMPLATES (Пресеты/Шаблоны)
-- ==========================================
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT UNIQUE NOT NULL,
    template_type TEXT NOT NULL CHECK(template_type IN ('preset', 'word', 'excel', 'pdf', 'email')),
    client_type TEXT CHECK(client_type IN ('TiA', 'FF', 'IP', 'all')),
    description TEXT,
    field_values_json TEXT,  -- JSON: {"awb_number": "12345678", "weight_kg": 100, ...}
    file_path TEXT,          -- Path to template file (for word/excel/pdf)
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(template_name);
CREATE INDEX IF NOT EXISTS idx_templates_type ON templates(template_type);
CREATE INDEX IF NOT EXISTS idx_templates_client_type ON templates(client_type);

-- ==========================================
-- SHIPMENTS (Отправления)
-- ==========================================
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    awb_number TEXT UNIQUE NOT NULL,
    shipment_type TEXT NOT NULL DEFAULT 'air' CHECK(shipment_type IN ('air', 'local_delivery')),
    shipment_date DATE NOT NULL,
    shipper_id INTEGER NOT NULL,
    consignee_id INTEGER NOT NULL,
    agent_id INTEGER,
    template_id INTEGER,
    weight_kg REAL NOT NULL CHECK(weight_kg > 0),
    pieces INTEGER NOT NULL CHECK(pieces > 0),
    volume_m3 REAL,
    goods_description TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'ready', 'sent', 'archived')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipper_id) REFERENCES parties(id) ON DELETE RESTRICT,
    FOREIGN KEY (consignee_id) REFERENCES parties(id) ON DELETE RESTRICT,
    FOREIGN KEY (agent_id) REFERENCES parties(id) ON DELETE SET NULL,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_shipments_awb ON shipments(awb_number);
CREATE INDEX IF NOT EXISTS idx_shipments_date ON shipments(shipment_date);
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
CREATE INDEX IF NOT EXISTS idx_shipments_shipper ON shipments(shipper_id);
CREATE INDEX IF NOT EXISTS idx_shipments_consignee ON shipments(consignee_id);
CREATE INDEX IF NOT EXISTS idx_shipments_type ON shipments(shipment_type);

-- ==========================================
-- DOCUMENTS (Документы)
-- ==========================================
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL,
    document_type TEXT NOT NULL CHECK(document_type IN ('awb', 'invoice', 'upd', 'invoice_tax', 'act', 'waybill', 'registry_1c')),
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,  -- SHA256 for integrity
    file_size INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'generated' CHECK(status IN ('generated', 'sent', 'archived')),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_shipment ON documents(shipment_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- ==========================================
-- EMAIL_DRAFTS (Черновики писем)
-- ==========================================
CREATE TABLE IF NOT EXISTS email_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    subject TEXT NOT NULL,
    body_html TEXT,
    body_text TEXT,
    attachments_json TEXT,  -- JSON: [{"path": "...", "name": "..."}]
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'sent', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_email_drafts_shipment ON email_drafts(shipment_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_status ON email_drafts(status);

-- ==========================================
-- AUDIT_LOG (Журнал изменений)
-- ==========================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'shipment', 'document', 'party', etc.
    entity_id INTEGER,
    action TEXT NOT NULL CHECK(action IN ('created', 'updated', 'deleted', 'sent', 'archived')),
    user_name TEXT NOT NULL DEFAULT 'system',
    old_values_json TEXT,  -- JSON: previous values
    new_values_json TEXT,  -- JSON: new values
    changes_json TEXT,     -- JSON: {"field": "weight_kg", "old": 100, "new": 150}
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

-- ==========================================
-- AWB_OVERLAY_CALIBRATION (Калибровка координат AWB)
-- ==========================================
CREATE TABLE IF NOT EXISTS awb_overlay_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    x_coord REAL NOT NULL,
    y_coord REAL NOT NULL,
    font_size REAL DEFAULT 10,
    font_name TEXT DEFAULT 'Helvetica',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_name, field_name)
);

CREATE INDEX IF NOT EXISTS idx_calibration_template ON awb_overlay_calibration(template_name);

-- ==========================================
-- ENVIRONMENT_DIAGNOSTICS (Диагностика окружения)
-- ==========================================
CREATE TABLE IF NOT EXISTS environment_diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT NOT NULL,
    check_type TEXT NOT NULL,  -- 'office', 'libreoffice', 'awb_editor'
    is_available INTEGER NOT NULL DEFAULT 0,
    version TEXT,
    path TEXT,
    details_json TEXT,
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diagnostics_type ON environment_diagnostics(check_type);

-- ==========================================
-- TRIGGERS for updated_at
-- ==========================================
CREATE TRIGGER IF NOT EXISTS update_parties_timestamp
AFTER UPDATE ON parties
BEGIN
    UPDATE parties SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_templates_timestamp
AFTER UPDATE ON templates
BEGIN
    UPDATE templates SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_shipments_timestamp
AFTER UPDATE ON shipments
BEGIN
    UPDATE shipments SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_calibration_timestamp
AFTER UPDATE ON awb_overlay_calibration
BEGIN
    UPDATE awb_overlay_calibration SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
