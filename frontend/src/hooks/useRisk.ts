import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface RiskScore {
  mmsi: number
  vessel_name: string | null
  ship_type: string | null
  overall_score: number
  risk_level: string
  identity_score: number
  flag_risk_score: number
  anomaly_score: number
  dark_history_score: number
  details: Record<string, any>
  scored_at: string
}

export async function computeRiskScore(mmsi: number): Promise<RiskScore> {
  const { data } = await axios.post(`${API_URL}/api/v1/risk/compute/${mmsi}`)
  return data
}

export async function getRiskScore(mmsi: number): Promise<RiskScore | null> {
  try {
    const { data } = await axios.get(`${API_URL}/api/v1/risk/score/${mmsi}`)
    return data
  } catch {
    return null
  }
}

export async function getHighRiskVessels(threshold = 50): Promise<RiskScore[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/risk/high-risk`, {
    params: { threshold },
  })
  return data.vessels
}

export function getReportUrl(mmsi: number): string {
  return `${API_URL}/api/v1/risk/report/${mmsi}`
}
