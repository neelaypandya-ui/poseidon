import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface AOI {
  id: number
  name: string
  description: string | null
  geojson: any
  active: boolean
  vessels_inside: number
  alert_vessel_types: string[]
  alert_min_risk_score: number
  created_at: string
}

export interface AOIEvent {
  id: number
  mmsi: number
  event_type: 'entry' | 'exit' | 'dwell'
  vessel_name: string | null
  ship_type: string | null
  lon: number | null
  lat: number | null
  sog: number | null
  occurred_at: string
}

export async function fetchAOIs(): Promise<AOI[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/aoi`)
  return data.areas
}

export async function createAOI(
  name: string,
  polygon: [number, number][],
  description?: string,
): Promise<AOI> {
  const { data } = await axios.post(`${API_URL}/api/v1/aoi`, {
    name,
    polygon,
    description,
  })
  return data
}

export async function deleteAOI(aoiId: number): Promise<void> {
  await axios.delete(`${API_URL}/api/v1/aoi/${aoiId}`)
}

export async function fetchAOIEvents(aoiId: number, limit = 50): Promise<AOIEvent[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/aoi/${aoiId}/events?limit=${limit}`)
  return data.events
}

export async function fetchAOIVessels(aoiId: number): Promise<any[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/aoi/${aoiId}/vessels`)
  return data.vessels
}
