-- Poseidon Phase 2.1: Sentinel-1 SAR Schema

-- SAR scenes — metadata for downloaded Sentinel-1 GRD products
CREATE TABLE sar_scenes (
    id                BIGSERIAL PRIMARY KEY,
    scene_id          TEXT UNIQUE NOT NULL,
    title             TEXT,
    platform          TEXT,
    acquisition_date  TIMESTAMPTZ NOT NULL,
    footprint         geometry(Polygon, 4326) NOT NULL,
    polarisation      TEXT,
    orbit_direction   TEXT,
    file_path         TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    detection_count   INT DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sar_scenes_footprint ON sar_scenes USING GIST (footprint);
CREATE INDEX idx_sar_scenes_acquisition ON sar_scenes (acquisition_date DESC);
CREATE INDEX idx_sar_scenes_status ON sar_scenes (status);

-- SAR detections — CFAR-detected objects from SAR imagery
CREATE TABLE sar_detections (
    id            BIGSERIAL PRIMARY KEY,
    scene_id      BIGINT NOT NULL REFERENCES sar_scenes(id) ON DELETE CASCADE,
    geom          geometry(Point, 4326) NOT NULL,
    rcs_db        REAL,
    pixel_size_m  REAL,
    confidence    REAL,
    matched       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sar_detections_geom ON sar_detections USING GIST (geom);
CREATE INDEX idx_sar_detections_scene ON sar_detections (scene_id);
CREATE INDEX idx_sar_detections_matched ON sar_detections (matched);

-- SAR vessel matches — linking CFAR detections to AIS vessels
CREATE TABLE sar_vessel_matches (
    id            BIGSERIAL PRIMARY KEY,
    detection_id  BIGINT NOT NULL REFERENCES sar_detections(id) ON DELETE CASCADE,
    mmsi          BIGINT NOT NULL REFERENCES vessels(mmsi),
    distance_m    REAL,
    time_delta_s  REAL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sar_matches_detection ON sar_vessel_matches (detection_id);
CREATE INDEX idx_sar_matches_mmsi ON sar_vessel_matches (mmsi);
