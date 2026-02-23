-- Phase 3: Intelligence Fusion tables

-- 3.1: Bayesian signal fusion results
CREATE TABLE IF NOT EXISTS signal_fusion_results (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT REFERENCES vessels(mmsi),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ais_confidence REAL DEFAULT 0,
    sar_confidence REAL DEFAULT 0,
    viirs_confidence REAL DEFAULT 0,
    acoustic_confidence REAL DEFAULT 0,
    rf_confidence REAL DEFAULT 0,
    posterior_score REAL DEFAULT 0,
    classification TEXT,
    intent_category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fusion_mmsi ON signal_fusion_results(mmsi);
CREATE INDEX IF NOT EXISTS idx_fusion_ts ON signal_fusion_results(timestamp DESC);

-- 3.2: Acoustic events from NOAA PMEL
CREATE TABLE IF NOT EXISTS acoustic_events (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'noaa_pmel',
    event_type TEXT,
    geom geometry(Point, 4326),
    bearing REAL,
    magnitude REAL,
    event_time TIMESTAMPTZ NOT NULL,
    raw_data JSONB,
    correlated_mmsi BIGINT,
    correlation_confidence REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_acoustic_geom ON acoustic_events USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_acoustic_time ON acoustic_events(event_time DESC);

-- 3.3: Route predictions (stores GeoJSON as JSONB for flexibility)
CREATE TABLE IF NOT EXISTS route_predictions (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT REFERENCES vessels(mmsi),
    predicted_at TIMESTAMPTZ DEFAULT NOW(),
    predicted_route JSONB,
    confidence_70 JSONB,
    confidence_90 JSONB,
    hours_ahead REAL DEFAULT 24,
    sog_used REAL,
    cog_used REAL,
    destination_port TEXT,
    eta TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_route_pred_mmsi ON route_predictions(mmsi);

-- 3.4: Vessel risk scores
CREATE TABLE IF NOT EXISTS vessel_risk_scores (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT REFERENCES vessels(mmsi),
    overall_score REAL NOT NULL,
    identity_score REAL DEFAULT 0,
    flag_risk_score REAL DEFAULT 0,
    anomaly_score REAL DEFAULT 0,
    dark_history_score REAL DEFAULT 0,
    risk_level TEXT,
    details JSONB,
    scored_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_risk_mmsi ON vessel_risk_scores(mmsi);
CREATE INDEX IF NOT EXISTS idx_risk_score ON vessel_risk_scores(overall_score DESC);

-- 3.5: Replay jobs
CREATE TABLE IF NOT EXISTS replay_jobs (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT,
    min_lon REAL,
    min_lat REAL,
    max_lon REAL,
    max_lat REAL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    speed REAL DEFAULT 10,
    status TEXT DEFAULT 'pending',
    total_frames INT DEFAULT 0,
    output_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
