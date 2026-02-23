import axios from 'axios'
import { useVesselStore } from '../stores/vesselStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

export async function predictRoute(mmsi: number, hours = 24): Promise<RoutePrediction> {
  const { data } = await axios.post(`${API_URL}/api/v1/routes/predict/${mmsi}`, null, {
    params: { hours },
  })
  useVesselStore.getState().setRoutePrediction(data)
  return data
}

export async function getPredictions(mmsi: number, limit = 5) {
  const { data } = await axios.get(`${API_URL}/api/v1/routes/predictions/${mmsi}`, {
    params: { limit },
  })
  return data.predictions
}
