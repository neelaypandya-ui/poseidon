-- Poseidon Phase 2.2: Sentinel-2 Optical Overlay + Timelapse Schema

-- Optical scenes — metadata for Sentinel-2 L2A products
CREATE TABLE optical_scenes (
    id                BIGSERIAL PRIMARY KEY,
    scene_id          TEXT UNIQUE NOT NULL,
    title             TEXT,
    platform          TEXT,
    acquisition_date  TIMESTAMPTZ NOT NULL,
    footprint         geometry(Polygon, 4326) NOT NULL,
    cloud_cover       REAL,
    file_path         TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_optical_scenes_footprint ON optical_scenes USING GIST (footprint);
CREATE INDEX idx_optical_scenes_acquisition ON optical_scenes (acquisition_date DESC);
CREATE INDEX idx_optical_scenes_status ON optical_scenes (status);

-- Timelapse jobs — track MP4 generation requests
CREATE TABLE timelapse_jobs (
    id              BIGSERIAL PRIMARY KEY,
    bbox_geom       geometry(Polygon, 4326) NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    composite_type  TEXT NOT NULL DEFAULT 'true-color',
    status          TEXT NOT NULL DEFAULT 'pending',
    scene_count     INT DEFAULT 0,
    output_path     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
