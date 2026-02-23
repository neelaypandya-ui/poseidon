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
}

export interface ViirsAnomaly {
  id: number
  lon: number
  lat: number
  bright_ti4: number
  bright_ti5: number | null
  frp: number | null
  confidence: string | null
  anomaly_type: string | null
  brightness_ratio: number | null
  detected_at: string
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

  // Replay state
  replayPlaying: boolean
  replayFrameIndex: number

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

  // Replay actions
  setReplayPlaying: (playing: boolean) => void
  setReplayFrameIndex: (index: number) => void
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

  replayPlaying: false,
  replayFrameIndex: 0,

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

  setReplayPlaying: (playing) => set({ replayPlaying: playing }),
  setReplayFrameIndex: (index) => set({ replayFrameIndex: index }),
}))
