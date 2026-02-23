# Poseidon — Claude Code Build Prompt
### Maritime Intelligence Platform

---

Build a maritime intelligence platform called **Poseidon** — a dark-themed, government-grade geospatial tracking system for monitoring global ship movements using exclusively free, public, and open data sources. The system is intended to support government agency use cases including sanctions enforcement, illegal fishing detection, environmental monitoring, and maritime domain awareness.

---

## STACK

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Map Engine | Deck.gl over MapLibre GL (WebGL-accelerated, handles millions of points) |
| Backend | FastAPI (Python) |
| Database | PostGIS (PostgreSQL with geospatial extensions) |
| Geospatial Indexing | H3 (Uber hexagonal grid) |
| Message Queue | Redis (for real-time feed buffering) |
| Containerization | Docker Compose |
| Visualization | Deck.gl ScatterplotLayer, TripsLayer, HeatmapLayer, IconLayer, PathLayer |
| Charts | Recharts |
| Styling | Tailwind CSS — dark navy theme, cyan/amber accent colors, neon glow effects |

---

## DATA SOURCES & APIs

### AIS (Vessel Position)

- **AISHub**: Free with antenna contribution OR receive-only access. REST API + UDP stream. Provides real-time vessel positions, MMSI, vessel name, speed, course, heading, nav status.
  - Endpoint: `http://data.aishub.net/ws.php`
- **aisstream.io**: Free WebSocket AIS stream, no contribution required. Use as primary real-time feed.
  - Endpoint: `wss://stream.aisstream.io/v0/stream`
- **VesselFinder** free tier: supplementary positions
- **MarineTraffic** free tier (25 credits/day): Use sparingly for vessel detail enrichment only

### SAR Satellite Imagery (Ship & Wake Detection)

- **ESA Copernicus Sentinel-1**: Free SAR imagery, global coverage, 6-12 day revisit. Access via Copernicus Data Space Ecosystem API.
  - Register at: `dataspace.copernicus.eu`
  - Use OpenSearch + STAC API for scene discovery
  - Process with: SNAP (ESA toolbox via snappy Python bindings) or pyroSAR for vessel detection and Kelvin wake extraction
  - Apply CFAR (Constant False Alarm Rate) detection algorithm for ship spotting independent of AIS

### Optical Satellite

- **Sentinel-2**: Free 10-meter resolution optical, use for port activity monitoring, vessel counting at anchorages, oil sheen detection. Access via same Copernicus Data Space API.
- **NASA Earthdata GIBS**: Real-time global imagery tiles, WMTS endpoint, free, no key required.
  - Endpoint: `https://gibs.earthdata.nasa.gov/wmts/`

### Nighttime Light (Fleet & Port Activity)

- **NASA VIIRS Black Marble**: Daily global nighttime light composite. Access via NASA LAADS DAAC, free with registration.
  - Use for: squid fishing fleet detection, port activity levels, illicit activity in unlit anchorages
- **FIRMS** (Fire Information for Resource Management System): Uses same sensor — useful for detecting vessel fires or industrial exhaust flares

### Acoustic / Hydrophone

- **NOAA PMEL Hydrophone Network**: Event bulletins and time-series data
  - Endpoints: `www.pmel.noaa.gov/acoustics/`
  - Access: FTP + HTTP, free
  - Parse event logs for detection timestamps and bearing estimates
  - Correlate events with AIS gaps in same geographic region ± 2 hours
- **IRIS Seismological Network**: Includes hydroacoustic stations. FDSN web services, free.
  - Endpoint: `https://service.iris.edu/fdsnws/`

### Oceanographic (Environmental Context)

- **NOAA National Buoy Data Center**: Real-time buoy data (wind, wave, current, temp) — correlates vessel behavior with sea state.
  - Endpoint: `https://www.ndbc.noaa.gov/data/realtime2/`
- **Copernicus Marine Service (CMEMS)**: Ocean current, SST, salinity, wave models — free with registration. Use for: drift modeling, current-adjusted route prediction, oil spill trajectory modeling.
- **Argo Float Program**: 4000+ autonomous floats, JSON API, free.
  - Endpoint: `https://argovis.colorado.edu/`

### Bathymetry (Navigability Constraints)

- **GEBCO 2023**: Global 15-arc-second ocean depth grid, free download.
  - Endpoint: `https://www.gebco.net/data_and_products/gridded_bathymetry_data/`
  - Use to: eliminate impossible vessel positions, constrain draft-based route prediction, identify choke points

### Port & Infrastructure Data

- **UN LOCODE**: Official port location database, free CSV download. 5000+ ports with coordinates, country, facilities.
- **OpenSeaMap**: Nautical chart overlays, free tiles + API. Endpoint: `http://tiles.openseamap.org/`
- **World Port Index (WWPII)**: NGIA/NGA free dataset, 3700+ ports with depth, facilities, services data

### Vessel Registry & Identity

- **ITU Ship Station List**: MMSI-to-vessel mappings, downloadable
- **IMO GISIS**: Limited public access for vessel particulars
- **Equasis**: Free vessel history, inspections, flag state — requires free registration (government-appropriate source)
- **OpenSanctions database**: Free, regularly updated sanctions lists including vessel SDN entries.
  - API: `https://api.opensanctions.org/`

### RF / Radar Context

No fully free RF emission data exists publicly. Implement placeholder layer with documented integration points for HawkEye360 or Spire Global APIs when agency licensing is obtained.

---

## CORE FEATURES

### 1. Live Vessel Map

- Real-time AIS rendering via aisstream.io WebSocket
- Vessel icons rotated to heading, colored by vessel type:
  - Tanker = amber
  - Cargo = cyan
  - Fishing = green
  - Unknown = red
- Click any vessel for full detail panel
- Trail rendering showing last 6/12/24 hours of track
- Speed-colored trails (faster = brighter)

### 2. Dark Vessel Detection Engine

Alert triggered when:
- AIS signal absent > 2 hours for vessel previously in coverage area
- Last known position extrapolated by heading + speed
- Search radius expands as time increases (uncertainty cone)
- Cross-reference against Sentinel-1 SAR detections in cone area
- Cross-reference against VIIRS nighttime light anomalies
- Output: confidence score 0–100, contributing signal breakdown

### 3. AIS Anomaly Detection

Flag the following behavioral anomalies:
- Speed inconsistency (reported speed vs. wake analysis)
- Position jumps (teleportation events — GPS spoofing indicator)
- Duplicate MMSI detection (two vessels claiming same identity)
- Loitering in open ocean (STS transfer indicator)
- Identity changes (vessel name/flag changes between port calls)
- Route deviation from declared destination
- Anchoring in unusual locations

### 4. Bayesian Signal Fusion Panel

For any vessel or area of interest:
- Display stacked horizontal confidence bars, one per active signal
- Signals: AIS, SAR, VIIRS, Acoustic, Oceanographic, Bathymetric constraint
- Overall posterior probability for vessel classification and intent category
- Timeline slider to replay fusion state at any past timestamp

### 5. SAR Integration Layer

- On-demand Sentinel-1 scene fetch for user-selected area + time range
- Automated CFAR ship detection overlay (detected objects as yellow diamonds)
- AIS correlation: match detected objects to known vessels by proximity + timing
- Unmatched SAR detections flagged as "ghost vessels"
- Kelvin wake extraction to estimate heading and speed of non-AIS vessels

### 6. Acoustic Event Correlation

- Parse NOAA PMEL event log for hydroacoustic detections
- Plot events on map as expanding sonar-ring animation
- Time-window correlation with AIS gaps in same basin region
- Display bearing estimate as arc overlay where available

### 7. VIIRS Nighttime Analysis

- Overlay Black Marble daily composite as optional map layer
- Automated anomaly detection: unexpected light clusters in open ocean (fishing fleets, illicit transfers)
- Port brightness index: trend chart showing port activity level over time (proxy for trade volume)
- Alert on significant brightness change at monitored ports

### 8. Route Prediction Engine

For any vessel, project forward route using:
- Current heading + speed (primary)
- Historical route patterns for this MMSI
- CMEMS ocean current adjustment
- GEBCO draft constraint (eliminate impossible routes)
- Declared destination (if AIS destination field populated)
- Render as probability cone with 70% / 90% confidence bands

### 9. Vessel Profile & Risk Scoring

For each vessel, aggregate:
- Identity verification (MMSI/IMO/name consistency check)
- Flag state risk tier (based on Paris MoU / Tokyo MoU deficiency rates)
- Sanctions cross-reference (OpenSanctions API, real-time)
- Port state control inspection history (Equasis)
- Behavioral anomaly history (past 90 days)
- Dark period history (frequency and duration of AIS gaps)
- Overall risk score 0–100, color coded green/amber/red
- Exportable PDF report per vessel

### 10. Area of Interest Monitoring

- User draws polygon on map
- System monitors all vessel entries/exits in real-time
- Configurable alerts: by vessel type, flag state, risk score, or AIS status
- Activity log with timestamps and vessel identities
- Dwell time analytics (which vessels spent the most time in zone)

---

## 4K / 2160P VIDEO INTEGRATION

### Port Webcam Aggregation

- Aggregate publicly accessible port and harbor webcam streams (many ports publish RTSP or HLS streams publicly)
- Embed video player panel that auto-selects the nearest public camera when a vessel approaches a monitored port
- Use ffmpeg.wasm (browser-side) for stream handling
- Display in 4K where source supports it, downscale gracefully

### Sentinel-2 Timelapse Video Export

For any selected area + date range, compile Sentinel-2 scenes into MP4 timelapse at 2160p resolution using:
- OpenCV + imageio for frame compilation
- True-color, false-color, and SWIR composite options
- Export button generates downloadable 4K video file
- Useful for: monitoring port construction, ice coverage change, oil spill spread, vessel accumulation at anchorages

### Replay Engine

- Any historical track or event sequence can be exported as 4K animated video
- Map renders at 2160p canvas resolution
- Deck.gl TripsLayer animates vessel movements
- Configurable playback speed (1x to 100x)
- Burned-in timestamp, signal overlay, and vessel labels
- Export via html2canvas + FFmpeg WASM pipeline

---

## COMPLIANCE & LEGAL FRAMEWORK

### Data Use Compliance

- Display attribution for all data sources per their license terms
- AIS data: used for situational awareness only, not retransmitted commercially without licensing
- Sentinel data: Copernicus open license, attribution required
- NOAA/NASA data: US government open data, no restriction
- Equasis: Terms prohibit bulk commercial resale — implement as per-vessel lookup only
- Implement data retention policy: raw AIS purged after 90 days, aggregated analytics retained indefinitely

### Maritime Law Compliance

- Platform is passive observation only — no transmission of signals, no interference with vessel navigation or communications
- AIS is a receive-only operation — fully legal globally
- SAR imagery analysis of public maritime zones: legal
- Clearly mark EEZ boundaries and territorial sea limits on map (12nm territorial, 24nm contiguous, 200nm EEZ)
- Flag when a vessel of interest crosses into territorial waters of a specific nation (jurisdictional handoff alert)

### Privacy & OPSEC

- No storage of individual crew member data
- Vessel position data for commercial vessels is public by law under SOLAS Chapter V
- Government use disclaimer in UI
- Audit log of all analyst queries and exports
- Role-based access control (admin, analyst, viewer)
- All API keys stored in environment variables, never in frontend

### Export Control

- Platform itself contains no ITAR/EAR controlled technology
- Flag for legal review before integrating any classified or controlled government data feeds into this system

---

## WEAKNESSES & MITIGATIONS

### AIS Spoofing
AIS positions can be faked. Mitigate by:
- Cross-validating AIS position against SAR detections
- Flagging positions that are physically impossible (speed > 50 knots, position jump > physics allow)
- Comparing reported draft/size against SAR-measured radar cross-section

### Coverage Gaps
Terrestrial AIS receivers don't cover open ocean. Mitigate by:
- Satellite AIS from aisstream.io partially covers this
- SAR detections fill gaps visually
- Acoustic events provide open-ocean detection
- Dead reckoning fills temporal gaps

### Data Latency
Some sources update minutes to hours behind real-time. Mitigate by:
- Display data freshness timestamp on every layer
- Color-fade stale data (positions older than 30 min shown dimmer)
- Clear labeling of "last updated" per signal type

### False Positives in Dark Vessel Detection
SAR detects stationary objects, birds, waves. Mitigate by:
- Minimum radar cross-section threshold for vessel classification
- Require corroboration from at least one additional signal
- Analyst review queue for low-confidence detections

### Single Point of Failure on Data Feeds
Mitigate by:
- Implement fallback sources for each layer
- Health monitoring dashboard showing feed status per source
- Graceful degradation: map remains functional if any single feed fails

### Acoustic Data Sparsity
Public hydrophone network is sparse. Mitigate by:
- Be explicit in UI about detection coverage zones
- Show hydrophone station locations and estimated detection radius
- Only correlate events within physically realistic bearing range

### Long-term Data Storage Costs
Mitigate by:
- Configurable data retention policies
- Tile caching for satellite imagery (don't re-fetch processed scenes)
- Aggregate historical tracks to lower resolution beyond 30 days

---

## UI/UX SPECIFICATION

| Element | Value |
|---|---|
| Background | `#050D1A` |
| Panel backgrounds | `#0A1628` |
| Active vessels (cyan) | `#00D4FF` |
| Alerts (amber) | `#FFB800` |
| Dark/high-risk (red) | `#FF3366` |
| Confirmed/safe (green) | `#00FF88` |

- Map fills full viewport, all panels float as collapsible overlays
- **Left sidebar**: layer controls (toggle each signal layer on/off)
- **Right sidebar**: selected vessel profile or area of interest report
- **Bottom timeline**: scrubber for historical replay with live/replay toggle
- **Top bar**: search by MMSI/vessel name, global alert count, feed health indicators
- Pulsing rings on dark vessel last-known positions
- Sonar sweep animation on acoustic detection events
- Subtle particle effects on vessel wakes at high zoom
- All panels exportable as PNG or PDF for briefing use

---

## GOVERNMENT DELIVERABLE FEATURES

- Scheduled automated reports (daily/weekly vessel activity digest for monitored zones) exportable as PDF
- Incident report generator: select a vessel + time range, auto-compile all signal data into a structured incident brief
- Sanctions hit alert system: real-time notification when a vessel matching OpenSanctions criteria enters a monitored zone
- Watchlist management: upload a list of MMSIs or vessel names, system alerts on any activity
- Chain of custody logging for all analyst actions (important for legal and evidentiary use)
- API endpoint for downstream integration with agency systems (REST, authenticated with JWT)

---

## PROJECT STRUCTURE

```
poseidon/
├── frontend/          # React + TypeScript + Deck.gl
├── backend/
│   ├── api/           # FastAPI routes
│   ├── ingestors/     # One module per data source
│   ├── processors/    # SAR processing, anomaly detection, fusion
│   ├── models/        # PostGIS schemas, Pydantic models
│   └── scheduler/     # APScheduler for periodic data pulls
├── db/                # PostGIS migrations
├── docker-compose.yml
├── .env.example       # All required API keys documented
└── README.md          # Full setup guide, data source attribution
```

---

## ENVIRONMENT VARIABLES

```env
# AIS
AISSTREAM_API_KEY=

# Copernicus / Sentinel
COPERNICUS_USERNAME=
COPERNICUS_PASSWORD=
COPERNICUS_CLIENT_ID=
COPERNICUS_CLIENT_SECRET=
COPERNICUS_S3_ACCESS_KEY=
COPERNICUS_S3_SECRET_KEY=

# Equasis
EQUASIS_EMAIL=
EQUASIS_PASSWORD=

# NASA
NASA_EARTHDATA_USERNAME=
NASA_EARTHDATA_PASSWORD=
NASA_EARTHDATA_TOKEN=

# MarineTraffic (free tier)
MARINETRAFFIC_API_KEY=

# OpenSanctions
OPENSANCTIONS_API_KEY=
```

---

## BUILD PHASES

### Phase 1 — Foundation (Start Here)
1. Docker Compose environment with PostGIS and Redis
2. AIS WebSocket ingestor from aisstream.io writing to PostGIS
3. MapLibre GL + Deck.gl base map with live vessel rendering
4. Basic vessel click → detail panel
5. Dark vessel detection (AIS gap > 2 hours) with uncertainty cone

### Phase 2 — Satellite Integration
1. Sentinel-1 SAR scene fetching and CFAR vessel detection
2. Ghost vessel flagging (SAR detections with no AIS match)
3. Sentinel-2 optical overlay and timelapse export
4. VIIRS nighttime light layer and anomaly detection

### Phase 3 — Intelligence Fusion
1. Bayesian signal fusion panel
2. Acoustic event correlation from NOAA PMEL
3. Route prediction engine with CMEMS current adjustment
4. Full vessel risk scoring and PDF report export
5. 4K replay engine and video export pipeline

---

> **Build incrementally. Test each ingestor independently before integrating into the map. Prioritize data pipeline stability over UI polish in early phases. Once Phase 1 vessels are rendering live, proceed to Phase 2, then Phase 3.**
