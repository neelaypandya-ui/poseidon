import axios from 'axios'
import { useVesselStore, type ViirsAnomaly } from '../stores/vesselStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchViirs(
  bbox?: [number, number, number, number],
  days = 1,
): Promise<void> {
  const params: Record<string, any> = { days }
  if (bbox) {
    params.min_lon = bbox[0]
    params.min_lat = bbox[1]
    params.max_lon = bbox[2]
    params.max_lat = bbox[3]
  }
  await axios.post(`${API_URL}/api/v1/viirs/fetch`, null, { params })
}

export async function fetchViirsAnomalies(
  bbox?: [number, number, number, number],
): Promise<ViirsAnomaly[]> {
  const params: Record<string, any> = {}
  if (bbox) {
    params.min_lon = bbox[0]
    params.min_lat = bbox[1]
    params.max_lon = bbox[2]
    params.max_lat = bbox[3]
  }
  const { data } = await axios.get(`${API_URL}/api/v1/viirs/anomalies`, { params })
  useVesselStore.getState().setViirsAnomalies(data.anomalies)
  return data.anomalies
}

export async function fetchViirsObservations(
  bbox?: [number, number, number, number],
  date?: string,
) {
  const params: Record<string, any> = {}
  if (bbox) {
    params.min_lon = bbox[0]
    params.min_lat = bbox[1]
    params.max_lon = bbox[2]
    params.max_lat = bbox[3]
  }
  if (date) params.date = date
  const { data } = await axios.get(`${API_URL}/api/v1/viirs/observations`, { params })
  return data.observations
}
