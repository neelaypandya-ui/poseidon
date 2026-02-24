import axios from 'axios'
import type { SpoofCluster } from '../stores/vesselStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchSpoofClusters(status = 'active'): Promise<SpoofCluster[]> {
  const { data } = await axios.get(
    `${API_URL}/api/v1/alerts/spoof-clusters?status=${status}`
  )
  return data.clusters
}

export async function fetchSpoofClusterDetail(clusterId: number) {
  const { data } = await axios.get(
    `${API_URL}/api/v1/alerts/spoof-clusters/${clusterId}`
  )
  return data
}

// --- Spoof-to-Dark Correlations ---

export interface CorrelationPair {
  spoof_signal: {
    id: number
    mmsi: number
    anomaly_type: string
    lon: number
    lat: number
    time: string | null
    details: any
  }
  dark_vessel: {
    alert_id: number
    mmsi: number
    name: string | null
    ship_type: string | null
    lon: number
    lat: number
    last_seen: string | null
    alert_detected: string | null
    gap_hours: number | null
  }
  correlation: {
    distance_nm: number | null
    time_gap_hours: number | null
  }
}

export interface CorrelationSummary {
  total_spoof_signals: number
  active_dark_alerts: number
  correlated_pairs: number
}

export async function fetchCorrelations(
  timeWindowHours = 2.0,
  spatialRadiusNm = 100.0,
  limit = 50
): Promise<CorrelationPair[]> {
  const { data } = await axios.get(
    `${API_URL}/api/v1/alerts/correlations?time_window_hours=${timeWindowHours}&spatial_radius_nm=${spatialRadiusNm}&limit=${limit}`
  )
  return data.correlations
}

export async function fetchCorrelationSummary(): Promise<CorrelationSummary> {
  const { data } = await axios.get(`${API_URL}/api/v1/alerts/correlations/summary`)
  return data
}

// --- Spoof Heatmap ---

export interface SpoofHeatmapPoint {
  lon: number
  lat: number
  anomaly_type: string
  weight: number
}

export async function fetchSpoofHeatmap(hours = 24): Promise<SpoofHeatmapPoint[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/heatmap/spoof?hours=${hours}`)
  return data.points
}
