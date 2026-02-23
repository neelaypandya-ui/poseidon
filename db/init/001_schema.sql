-- Poseidon Phase 1 Schema
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enums
CREATE TYPE vessel_type AS ENUM (
    'cargo', 'tanker', 'fishing', 'passenger', 'tug',
    'pleasure', 'military', 'sar', 'hsc', 'unknown'
);

CREATE TYPE nav_status AS ENUM (
    'under_way_using_engine', 'at_anchor', 'not_under_command',
    'restricted_manoeuvrability', 'constrained_by_draught',
    'moored', 'aground', 'engaged_in_fishing',
    'under_way_sailing', 'reserved_hsc', 'reserved_wing',
    'power_driven_towing_astern', 'power_driven_pushing',
    'reserved_13', 'ais_sart', 'not_defined'
);

CREATE TYPE alert_status AS ENUM ('active', 'resolved');

-- Vessels (static metadata)
CREATE TABLE vessels (
    mmsi        BIGINT PRIMARY KEY,
    imo         BIGINT,
    name        TEXT,
    callsign    TEXT,
    ship_type   vessel_type NOT NULL DEFAULT 'unknown',
    ais_type_code INTEGER,
    dim_bow     SMALLINT,
    dim_stern   SMALLINT,
    dim_port    SMALLINT,
    dim_starboard SMALLINT,
    destination TEXT,
    eta         TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vessels_name_trgm ON vessels USING gin (name gin_trgm_ops);

-- Vessel positions (time-series)
CREATE TABLE vessel_positions (
    id          BIGSERIAL PRIMARY KEY,
    mmsi        BIGINT NOT NULL REFERENCES vessels(mmsi) ON DELETE CASCADE,
    geom        geometry(Point, 4326) NOT NULL,
    h3_index    TEXT,
    sog         REAL,
    cog         REAL,
    heading     SMALLINT,
    nav_status  nav_status,
    rot         REAL,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_positions_mmsi_ts ON vessel_positions (mmsi, timestamp DESC);
CREATE INDEX idx_positions_geom ON vessel_positions USING GIST (geom);
CREATE INDEX idx_positions_timestamp ON vessel_positions (timestamp DESC);

-- Latest vessel positions (one row per vessel, trigger-maintained)
CREATE TABLE latest_vessel_positions (
    mmsi        BIGINT PRIMARY KEY REFERENCES vessels(mmsi) ON DELETE CASCADE,
    geom        geometry(Point, 4326) NOT NULL,
    h3_index    TEXT,
    sog         REAL,
    cog         REAL,
    heading     SMALLINT,
    nav_status  nav_status,
    timestamp   TIMESTAMPTZ NOT NULL,
    name        TEXT,
    ship_type   vessel_type NOT NULL DEFAULT 'unknown',
    destination TEXT
);

CREATE INDEX idx_latest_geom ON latest_vessel_positions USING GIST (geom);

-- Trigger function: upsert latest position after each insert
CREATE OR REPLACE FUNCTION upsert_latest_position()
RETURNS TRIGGER AS $$
DECLARE
    v_name TEXT;
    v_ship_type vessel_type;
    v_destination TEXT;
BEGIN
    SELECT name, ship_type, destination
    INTO v_name, v_ship_type, v_destination
    FROM vessels WHERE mmsi = NEW.mmsi;

    INSERT INTO latest_vessel_positions
        (mmsi, geom, h3_index, sog, cog, heading, nav_status, timestamp, name, ship_type, destination)
    VALUES
        (NEW.mmsi, NEW.geom, NEW.h3_index, NEW.sog, NEW.cog, NEW.heading,
         NEW.nav_status, NEW.timestamp, v_name, v_ship_type, v_destination)
    ON CONFLICT (mmsi) DO UPDATE SET
        geom = EXCLUDED.geom,
        h3_index = EXCLUDED.h3_index,
        sog = EXCLUDED.sog,
        cog = EXCLUDED.cog,
        heading = EXCLUDED.heading,
        nav_status = EXCLUDED.nav_status,
        timestamp = EXCLUDED.timestamp,
        name = EXCLUDED.name,
        ship_type = EXCLUDED.ship_type,
        destination = EXCLUDED.destination
    WHERE EXCLUDED.timestamp > latest_vessel_positions.timestamp;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_upsert_latest_position
    AFTER INSERT ON vessel_positions
    FOR EACH ROW
    EXECUTE FUNCTION upsert_latest_position();

-- Dark vessel alerts
CREATE TABLE dark_vessel_alerts (
    id              BIGSERIAL PRIMARY KEY,
    mmsi            BIGINT NOT NULL REFERENCES vessels(mmsi) ON DELETE CASCADE,
    status          alert_status NOT NULL DEFAULT 'active',
    last_known_geom geometry(Point, 4326) NOT NULL,
    predicted_geom  geometry(Point, 4326),
    last_sog        REAL,
    last_cog        REAL,
    gap_hours       REAL,
    search_radius_nm REAL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dark_alerts_status ON dark_vessel_alerts (status) WHERE status = 'active';
CREATE INDEX idx_dark_alerts_mmsi ON dark_vessel_alerts (mmsi, detected_at DESC);
