-- Phase 2.3: VIIRS Nighttime Light observations & anomaly detection

CREATE TABLE viirs_observations (
    id BIGSERIAL PRIMARY KEY,
    geom geometry(Point, 4326) NOT NULL,
    radiance REAL NOT NULL,
    observation_date DATE NOT NULL,
    tile_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_viirs_geom ON viirs_observations USING GIST (geom);
CREATE INDEX idx_viirs_date ON viirs_observations (observation_date DESC);

CREATE TABLE viirs_anomalies (
    id BIGSERIAL PRIMARY KEY,
    geom geometry(Point, 4326) NOT NULL,
    radiance REAL NOT NULL,
    baseline_radiance REAL,
    anomaly_ratio REAL,
    observation_date DATE NOT NULL,
    anomaly_type TEXT DEFAULT 'brightness',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_viirs_anomalies_geom ON viirs_anomalies USING GIST (geom);
CREATE INDEX idx_viirs_anomalies_date ON viirs_anomalies (observation_date DESC);
