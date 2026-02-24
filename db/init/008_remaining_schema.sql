-- ============================================================
-- 008_remaining_schema.sql
-- Poseidon Phase 4: Remaining 12 features
-- ============================================================

-- ===================== EEZ Zones =============================
CREATE TABLE IF NOT EXISTS eez_zones (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    sovereign     TEXT,
    iso_ter1      TEXT,
    mrgid         INTEGER,
    area_km2      DOUBLE PRECISION,
    geom          GEOMETRY(MultiPolygon, 4326),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_eez_zones_geom ON eez_zones USING GIST (geom);

-- EEZ entry/exit events
CREATE TABLE IF NOT EXISTS eez_entry_events (
    id            SERIAL PRIMARY KEY,
    mmsi          INTEGER NOT NULL REFERENCES vessels(mmsi),
    eez_id        INTEGER REFERENCES eez_zones(id),
    eez_name      TEXT,
    event_type    TEXT NOT NULL CHECK (event_type IN ('entry', 'exit')),
    geom          GEOMETRY(Point, 4326),
    timestamp     TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_eez_entry_events_mmsi ON eez_entry_events (mmsi);
CREATE INDEX IF NOT EXISTS idx_eez_entry_events_ts ON eez_entry_events (timestamp DESC);

-- ===================== Ports =================================
CREATE TABLE IF NOT EXISTS ports (
    id            SERIAL PRIMARY KEY,
    locode        TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    country_code  TEXT,
    country_name  TEXT,
    geom          GEOMETRY(Point, 4326),
    port_size     TEXT DEFAULT 'small',
    port_type     TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ports_geom ON ports USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ports_country ON ports (country_code);

-- ===================== Users (JWT Auth) ======================
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('admin', 'analyst', 'viewer')),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

-- ===================== Audit Log =============================
CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id),
    username      TEXT,
    method        TEXT NOT NULL,
    path          TEXT NOT NULL,
    status_code   INTEGER,
    client_ip     TEXT,
    user_agent    TEXT,
    request_body  JSONB,
    response_time_ms DOUBLE PRECISION,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_path ON audit_log (path);

-- ===================== Scheduled Reports =====================
CREATE TABLE IF NOT EXISTS scheduled_reports (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    report_type   TEXT NOT NULL DEFAULT 'daily_digest',
    schedule_cron TEXT NOT NULL DEFAULT '0 6 * * *',
    config        JSONB DEFAULT '{}',
    enabled       BOOLEAN DEFAULT TRUE,
    last_run_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduled_report_outputs (
    id            SERIAL PRIMARY KEY,
    report_id     INTEGER REFERENCES scheduled_reports(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'pending',
    pdf_path      TEXT,
    summary       JSONB,
    generated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_outputs_report ON scheduled_report_outputs (report_id);

-- ===================== Kelvin Wake Detections ================
CREATE TABLE IF NOT EXISTS kelvin_wake_detections (
    id            SERIAL PRIMARY KEY,
    scene_id      INTEGER REFERENCES sar_scenes(id),
    geom          GEOMETRY(Point, 4326),
    wake_angle_deg DOUBLE PRECISION,
    estimated_speed_knots DOUBLE PRECISION,
    confidence    DOUBLE PRECISION,
    matched_mmsi  INTEGER,
    detected_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kelvin_wake_geom ON kelvin_wake_detections USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_kelvin_wake_scene ON kelvin_wake_detections (scene_id);

-- ===================== Port Webcams ==========================
CREATE TABLE IF NOT EXISTS port_webcams (
    id            SERIAL PRIMARY KEY,
    port_locode   TEXT REFERENCES ports(locode),
    name          TEXT NOT NULL UNIQUE,
    stream_url    TEXT NOT NULL,
    thumbnail_url TEXT,
    geom          GEOMETRY(Point, 4326),
    country_code  TEXT,
    status        TEXT DEFAULT 'active',
    last_checked  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_webcams_geom ON port_webcams USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_webcams_port ON port_webcams (port_locode);
