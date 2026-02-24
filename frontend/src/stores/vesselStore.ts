import { create } from 'zustand'

export interface Vessel {
  mmsi: number
  name: string | null
  ship_type: string
  destination: string | null
  lon: number
  lat: number
  sog: number | null
  cog: number | null
  heading: number | null
  nav_status: string | null
  timestamp: string
}

export interface DarkAlert {
  id: number
  mmsi: number
  vessel_name: string | null
  ship_type: string | null
  last_known_lon: number
  last_known_lat: number
  predicted_lon: number | null
  predicted_lat: number | null
  last_sog: number | null
  last_cog: number | null
  gap_hours: number | null
  search_radius_nm: number | null
  last_seen_at: string
  detected_at: string
}

export interface TrackPoint {
  lon: number
  lat: number
  sog: number | null
  cog: number | null
  timestamp: string
}

export interface SarScene {
  id: number
  scene_id: string
  title: string
  platform: string
  acquisition_date: string
  polarisation: string
  orbit_direction: string
  status: string
  detection_count: number
  footprint: object | null
}

export interface SarDetection {
  id: number
  scene_id: number
  lon: number
  lat: number
  rcs_db: number | null
  pixel_size_m: number | null
  confidence: number | null
  matched: boolean
}

export interface OpticalScene {
  id: number
  scene_id: string
  title: string
  platform: string
  acquisition_date: string
  cloud_cover: number | null
  status: string
  file_path: string | null
}

export interface SpoofCluster {
  id: number
  signal_count: number
  centroid_lon: number
  centroid_lat: number
  radius_nm: number | null
  window_start: string
  window_end: string
  anomaly_types: string[]
  status: string
  created_at: string
}

export interface RoutePrediction {
  mmsi: number
  route_geom: [number, number][]
  confidence_70: any | null
  confidence_90: any | null
  eta: string | null
  predicted_at: string
  hours_ahead: number
  vessel_name: string | null
  ship_type: string | null
  sog_used: number
  cog_used: number
  destination_name: string | null
  destination_coords: [number, number] | null
}

export interface ViirsAnomaly {
  id: number
  lon: number
  lat: number
  radiance: number
  baseline_radiance: number | null
  anomaly_ratio: number | null
  anomaly_type: string | null
  observation_date: string
}

export interface ForensicPing {
  id: number
  lon: number
  lat: number
  flagged: boolean
  timestamp: string
}

export interface AcousticEvent {
  id: number
  source: string
  event_type: string
  lon: number | null
  lat: number | null
  bearing: number | null
  magnitude: number | null
  event_time: string
  correlated_mmsi: number | null
  correlation_confidence: number | null
}

interface VesselState {
  vessels: Map<number, Vessel>
  vesselCount: number
  selectedMmsi: number | null
  selectedTrack: TrackPoint[]
  darkAlerts: DarkAlert[]
  vesselLayerVisible: boolean
  searchQuery: string
  filteredCount: number

  // SAR state
  sarScenes: SarScene[]
  sarDetections: SarDetection[]
  sarLayerVisible: boolean
  ghostVesselLayerVisible: boolean

  // Optical state
  opticalScenes: OpticalScene[]

  // VIIRS state
  viirsAnomalies: ViirsAnomaly[]
  viirsLayerVisible: boolean

  // Route prediction state
  routePrediction: RoutePrediction | null
  routeLayerVisible: boolean

  // Dark alert layer toggle
  darkAlertLayerVisible: boolean

  // Risk / fusion filter state
  criticalRiskMmsis: Set<number>
  lowConfidenceMmsis: Set<number>
  riskFusionFilter: 'all' | 'critical' | 'low_confidence'

  // Spoof state
  spoofClusters: SpoofCluster[]
  spoofLayerVisible: boolean
  spoofHeatmapVisible: boolean
  spoofHeatmapData: { lon: number; lat: number; weight: number }[]

  // Correlation state
  correlationCount: number

  // Maritime overlay state
  shippingLaneLayerVisible: boolean

  // AOI state
  drawingAoi: boolean
  aoiPolygonPoints: [number, number][]
  aoiGeoJsons: any[]

  // Replay state
  replayPlaying: boolean
  replayFrameIndex: number

  // EEZ layer state
  eezLayerVisible: boolean
  eezData: any | null

  // Ports layer state
  portsLayerVisible: boolean
  portsData: any | null

  // Bathymetry layer state
  bathymetryLayerVisible: boolean

  // Acoustic events state
  acousticEvents: AcousticEvent[]
  acousticLayerVisible: boolean

  // Webcam markers state
  webcamLayerVisible: boolean

  // Forensic pings state
  forensicPings: ForensicPing[]

  setVessels: (vessels: Vessel[]) => void
  updateVessel: (vessel: Vessel) => void
  batchUpdateVessels: (vessels: Vessel[]) => void
  setSelectedMmsi: (mmsi: number | null) => void
  setSelectedTrack: (track: TrackPoint[]) => void
  setDarkAlerts: (alerts: DarkAlert[]) => void
  setVesselLayerVisible: (visible: boolean) => void
  setSearchQuery: (query: string) => void
  setFilteredCount: (count: number) => void

  // SAR actions
  setSarScenes: (scenes: SarScene[]) => void
  setSarDetections: (detections: SarDetection[]) => void
  toggleSarLayer: () => void
  toggleGhostVesselLayer: () => void

  // Optical actions
  setOpticalScenes: (scenes: OpticalScene[]) => void

  // VIIRS actions
  setViirsAnomalies: (anomalies: ViirsAnomaly[]) => void
  toggleViirsLayer: () => void

  // Route prediction actions
  setRoutePrediction: (pred: RoutePrediction | null) => void
  toggleRouteLayer: () => void

  // Dark alert layer actions
  toggleDarkAlertLayer: () => void

  // Risk / fusion filter actions
  setCriticalRiskMmsis: (mmsis: Set<number>) => void
  setLowConfidenceMmsis: (mmsis: Set<number>) => void
  setRiskFusionFilter: (filter: 'all' | 'critical' | 'low_confidence') => void

  // Spoof actions
  setSpoofClusters: (clusters: SpoofCluster[]) => void
  toggleSpoofLayer: () => void
  toggleSpoofHeatmap: () => void
  setSpoofHeatmapData: (data: { lon: number; lat: number; weight: number }[]) => void

  // Correlation actions
  setCorrelationCount: (count: number) => void

  // Maritime overlay actions
  toggleShippingLaneLayer: () => void

  // AOI actions
  setDrawingAoi: (drawing: boolean) => void
  setAoiPolygonPoints: (points: [number, number][]) => void
  setAoiGeoJsons: (geojsons: any[]) => void

  // Replay actions
  setReplayPlaying: (playing: boolean) => void
  setReplayFrameIndex: (index: number) => void

  // EEZ actions
  toggleEezLayer: () => void
  setEezData: (data: any) => void

  // Ports actions
  togglePortsLayer: () => void
  setPortsData: (data: any) => void

  // Bathymetry actions
  toggleBathymetryLayer: () => void

  // Acoustic actions
  setAcousticEvents: (events: AcousticEvent[]) => void
  toggleAcousticLayer: () => void

  // Webcam actions
  toggleWebcamLayer: () => void

  // Forensic pings actions
  setForensicPings: (pings: ForensicPing[]) => void
}

export const useVesselStore = create<VesselState>((set) => ({
  vessels: new Map(),
  vesselCount: 0,
  selectedMmsi: null,
  selectedTrack: [],
  darkAlerts: [],
  vesselLayerVisible: true,
  searchQuery: '',
  filteredCount: 0,

  sarScenes: [],
  sarDetections: [],
  sarLayerVisible: true,
  ghostVesselLayerVisible: true,

  opticalScenes: [],

  viirsAnomalies: [],
  viirsLayerVisible: true,

  routePrediction: null,
  routeLayerVisible: true,

  darkAlertLayerVisible: true,

  criticalRiskMmsis: new Set(),
  lowConfidenceMmsis: new Set(),
  riskFusionFilter: 'all',

  spoofClusters: [],
  spoofLayerVisible: true,
  spoofHeatmapVisible: false,
  spoofHeatmapData: [],

  correlationCount: 0,

  shippingLaneLayerVisible: false,

  drawingAoi: false,
  aoiPolygonPoints: [],
  aoiGeoJsons: [],

  replayPlaying: false,
  replayFrameIndex: 0,

  // New layer defaults
  eezLayerVisible: false,
  eezData: null,

  portsLayerVisible: false,
  portsData: null,

  bathymetryLayerVisible: true,

  acousticEvents: [],
  acousticLayerVisible: true,

  webcamLayerVisible: false,

  forensicPings: [],

  setVessels: (vessels) =>
    set(() => {
      const map = new Map<number, Vessel>()
      vessels.forEach((v) => map.set(v.mmsi, v))
      console.log('[Poseidon] Vessel count:', map.size)
      return { vessels: map, vesselCount: map.size }
    }),

  updateVessel: (vessel) =>
    set((state) => {
      const newMap = new Map(state.vessels)
      newMap.set(vessel.mmsi, vessel)
      return { vessels: newMap, vesselCount: newMap.size }
    }),

  batchUpdateVessels: (batch) =>
    set((state) => {
      const newMap = new Map(state.vessels)
      for (const v of batch) {
        newMap.set(v.mmsi, v)
      }
      return { vessels: newMap, vesselCount: newMap.size }
    }),

  setSelectedMmsi: (mmsi) => set({ selectedMmsi: mmsi }),
  setSelectedTrack: (track) => set({ selectedTrack: track }),
  setDarkAlerts: (alerts) => set({ darkAlerts: alerts }),
  setVesselLayerVisible: (visible) => set({ vesselLayerVisible: visible }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setFilteredCount: (count) => set({ filteredCount: count }),

  setSarScenes: (scenes) => set({ sarScenes: scenes }),
  setSarDetections: (detections) => set({ sarDetections: detections }),
  toggleSarLayer: () => set((s) => ({ sarLayerVisible: !s.sarLayerVisible })),
  toggleGhostVesselLayer: () => set((s) => ({ ghostVesselLayerVisible: !s.ghostVesselLayerVisible })),

  setOpticalScenes: (scenes) => set({ opticalScenes: scenes }),

  setViirsAnomalies: (anomalies) => set({ viirsAnomalies: anomalies }),
  toggleViirsLayer: () => set((s) => ({ viirsLayerVisible: !s.viirsLayerVisible })),

  setRoutePrediction: (pred) => set({ routePrediction: pred }),
  toggleRouteLayer: () => set((s) => ({ routeLayerVisible: !s.routeLayerVisible })),

  toggleDarkAlertLayer: () => set((s) => ({ darkAlertLayerVisible: !s.darkAlertLayerVisible })),

  setCriticalRiskMmsis: (mmsis) => set({ criticalRiskMmsis: mmsis }),
  setLowConfidenceMmsis: (mmsis) => set({ lowConfidenceMmsis: mmsis }),
  setRiskFusionFilter: (filter) => set({ riskFusionFilter: filter }),

  setSpoofClusters: (clusters) => set({ spoofClusters: clusters }),
  toggleSpoofLayer: () => set((s) => ({ spoofLayerVisible: !s.spoofLayerVisible })),
  toggleSpoofHeatmap: () => set((s) => ({ spoofHeatmapVisible: !s.spoofHeatmapVisible })),
  setSpoofHeatmapData: (data) => set({ spoofHeatmapData: data }),

  setCorrelationCount: (count) => set({ correlationCount: count }),

  toggleShippingLaneLayer: () => set((s) => ({ shippingLaneLayerVisible: !s.shippingLaneLayerVisible })),

  setDrawingAoi: (drawing) => set({ drawingAoi: drawing }),
  setAoiPolygonPoints: (points) => set({ aoiPolygonPoints: points }),
  setAoiGeoJsons: (geojsons) => set({ aoiGeoJsons: geojsons }),

  setReplayPlaying: (playing) => set({ replayPlaying: playing }),
  setReplayFrameIndex: (index) => set({ replayFrameIndex: index }),

  // New layer actions
  toggleEezLayer: () => set((s) => ({ eezLayerVisible: !s.eezLayerVisible })),
  setEezData: (data) => set({ eezData: data }),

  togglePortsLayer: () => set((s) => ({ portsLayerVisible: !s.portsLayerVisible })),
  setPortsData: (data) => set({ portsData: data }),

  toggleBathymetryLayer: () => set((s) => ({ bathymetryLayerVisible: !s.bathymetryLayerVisible })),

  setAcousticEvents: (events) => set({ acousticEvents: events }),
  toggleAcousticLayer: () => set((s) => ({ acousticLayerVisible: !s.acousticLayerVisible })),

  toggleWebcamLayer: () => set((s) => ({ webcamLayerVisible: !s.webcamLayerVisible })),

  setForensicPings: (pings) => set({ forensicPings: pings }),
}))
