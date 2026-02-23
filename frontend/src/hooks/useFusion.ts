import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface FusionResult {
  id: number
  mmsi: number
  timestamp: string
  ais_confidence: number
  sar_confidence: number
  viirs_confidence: number
  acoustic_confidence: number
  posterior_score: number
  classification: string
}

export async function computeFusion(mmsi: number): Promise<FusionResult> {
  const { data } = await axios.post(`${API_URL}/api/v1/fusion/compute/${mmsi}`)
  return data
}

export async function getFusionHistory(mmsi: number, limit = 20): Promise<FusionResult[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/fusion/history/${mmsi}`, {
    params: { limit },
  })
  return data
}

export async function fetchFusionBatch(hours = 24): Promise<FusionResult[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/fusion/batch`, {
    params: { hours },
  })
  return data
}
