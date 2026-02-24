-- Tier 3: Watchlist, Area of Interest, Sanctions, Incident Reports
-- Apply manually: docker exec -i poseidon-postgis-1 psql -U poseidon -d poseidon < db/init/007_tier3_schema.sql

-- ============================================================
-- Watchlist: vessels under active monitoring
-- ============================================================
CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT NOT NULL,
    label TEXT,
    reason TEXT,
    alert_on_position BOOLEAN DEFAULT TRUE,
    alert_on_dark BOOLEAN DEFAULT TRUE,
    alert_on_spoof BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mmsi)
);

-- ============================================================
-- Sanctions match cache
-- ============================================================
CREATE TABLE IF NOT EXISTS sanctions_matches (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT,
    imo BIGINT,
    vessel_name TEXT,
    entity_id TEXT NOT NULL,
    entity_name TEXT,
    datasets TEXT[],
    match_score REAL,
    properties JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sanctions_mmsi ON sanctions_matches(mmsi);
CREATE INDEX IF NOT EXISTS idx_sanctions_imo ON sanctions_matches(imo);

-- ============================================================
-- Equasis vessel detail cache
-- ============================================================
CREATE TABLE IF NOT EXISTS equasis_cache (
    id BIGSERIAL PRIMARY KEY,
    imo BIGINT UNIQUE NOT NULL,
    vessel_name TEXT,
    flag_state TEXT,
    gross_tonnage REAL,
    deadweight REAL,
    year_built INT,
    registered_owner TEXT,
    operator TEXT,
    class_society TEXT,
    inspections JSONB DEFAULT '[]',
    flag_history JSONB DEFAULT '[]',
    raw_html TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Areas of Interest
-- ============================================================
CREATE TABLE IF NOT EXISTS areas_of_interest (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    geom geometry(Polygon, 4326) NOT NULL,
    alert_vessel_types TEXT[] DEFAULT '{}',
    alert_min_risk_score INT DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_aoi_geom ON areas_of_interest USING GIST(geom);

CREATE TABLE IF NOT EXISTS aoi_events (
    id BIGSERIAL PRIMARY KEY,
    aoi_id BIGINT NOT NULL REFERENCES areas_of_interest(id) ON DELETE CASCADE,
    mmsi BIGINT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('entry', 'exit', 'dwell')),
    vessel_name TEXT,
    ship_type TEXT,
    lon REAL,
    lat REAL,
    sog REAL,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_aoi_events_aoi ON aoi_events(aoi_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_aoi_events_mmsi ON aoi_events(mmsi, occurred_at DESC);

-- Track which vessels are currently inside each AOI
CREATE TABLE IF NOT EXISTS aoi_vessel_presence (
    aoi_id BIGINT NOT NULL REFERENCES areas_of_interest(id) ON DELETE CASCADE,
    mmsi BIGINT NOT NULL,
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (aoi_id, mmsi)
);

-- ============================================================
-- Incident reports
-- ============================================================
CREATE TABLE IF NOT EXISTS incident_reports (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT,
    title TEXT NOT NULL,
    report_type TEXT DEFAULT 'vessel',
    content JSONB NOT NULL,
    pdf_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_mmsi ON incident_reports(mmsi, created_at DESC);
