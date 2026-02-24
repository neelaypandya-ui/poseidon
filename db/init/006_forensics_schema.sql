-- Poseidon Phase 4: AIS Signal Forensics Schema

-- Feature 1: Receiver classification
DO $$ BEGIN
    CREATE TYPE receiver_class AS ENUM ('terrestrial', 'satellite', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE vessel_positions ADD COLUMN IF NOT EXISTS receiver_class receiver_class DEFAULT 'unknown';

-- Feature 2: Raw message forensics store
CREATE TABLE IF NOT EXISTS ais_raw_messages (
    id              BIGSERIAL PRIMARY KEY,
    mmsi            BIGINT NOT NULL,
    message_type    TEXT NOT NULL,
    raw_json        JSONB NOT NULL,
    flag_impossible_speed   BOOLEAN DEFAULT FALSE,
    flag_sart_on_non_sar    BOOLEAN DEFAULT FALSE,
    flag_no_identity        BOOLEAN DEFAULT FALSE,
    flag_position_jump      BOOLEAN DEFAULT FALSE,
    prev_distance_nm        REAL,
    implied_speed_knots     REAL,
    receiver_class  receiver_class DEFAULT 'unknown',
    lat             REAL,
    lon             REAL,
    sog             REAL,
    timestamp       TIMESTAMPTZ,
    received_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_mmsi_ts ON ais_raw_messages (mmsi, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_raw_messages_flagged ON ais_raw_messages (mmsi, timestamp DESC)
    WHERE flag_impossible_speed OR flag_sart_on_non_sar OR flag_no_identity OR flag_position_jump;
CREATE INDEX IF NOT EXISTS idx_raw_messages_time ON ais_raw_messages (received_at DESC);

-- Feature 3: Vessel identity history
CREATE TABLE IF NOT EXISTS vessel_identity_history (
    id              BIGSERIAL PRIMARY KEY,
    mmsi            BIGINT NOT NULL REFERENCES vessels(mmsi) ON DELETE CASCADE,
    name            TEXT,
    ship_type       vessel_type,
    callsign        TEXT,
    imo             BIGINT,
    destination     TEXT,
    observed_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_identity_hist_mmsi ON vessel_identity_history (mmsi, observed_at DESC);

-- Feature 4: Spoof cluster detection
DO $$ BEGIN
    CREATE TYPE spoof_anomaly_type AS ENUM (
        'impossible_speed', 'sart_on_non_sar', 'position_jump', 'no_identity'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS spoof_signals (
    id              BIGSERIAL PRIMARY KEY,
    mmsi            BIGINT NOT NULL REFERENCES vessels(mmsi) ON DELETE CASCADE,
    anomaly_type    spoof_anomaly_type NOT NULL,
    geom            geometry(Point, 4326) NOT NULL,
    sog             REAL,
    cog             REAL,
    nav_status      nav_status,
    details         JSONB,
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    cluster_id      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_spoof_signals_time ON spoof_signals (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_spoof_signals_cluster ON spoof_signals (cluster_id);
CREATE INDEX IF NOT EXISTS idx_spoof_signals_geom ON spoof_signals USING GIST (geom);

CREATE TABLE IF NOT EXISTS spoof_clusters (
    id              BIGSERIAL PRIMARY KEY,
    signal_count    INT DEFAULT 0,
    centroid        geometry(Point, 4326),
    radius_nm       REAL,
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    anomaly_types   TEXT[],
    status          alert_status DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_spoof_clusters_active ON spoof_clusters (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_spoof_clusters_time ON spoof_clusters (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spoof_clusters_geom ON spoof_clusters USING GIST (centroid);
