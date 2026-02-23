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

interface VesselState {
  vessels: Map<number, Vessel>
  vesselCount: number
  selectedMmsi: number | null
  selectedTrack: TrackPoint[]
  darkAlerts: DarkAlert[]
  vesselLayerVisible: boolean
  searchQuery: string
  filteredCount: number

  setVessels: (vessels: Vessel[]) => void
  updateVessel: (vessel: Vessel) => void
  batchUpdateVessels: (vessels: Vessel[]) => void
  setSelectedMmsi: (mmsi: number | null) => void
  setSelectedTrack: (track: TrackPoint[]) => void
  setDarkAlerts: (alerts: DarkAlert[]) => void
  setVesselLayerVisible: (visible: boolean) => void
  setSearchQuery: (query: string) => void
  setFilteredCount: (count: number) => void
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
}))
