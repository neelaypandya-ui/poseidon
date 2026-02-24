import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface WatchlistItem {
  id: number
  mmsi: number
  label: string | null
  reason: string | null
  vessel_name: string | null
  ship_type: string | null
  imo: number | null
  lon: number | null
  lat: number | null
  sog: number | null
  nav_status: string | null
  last_seen: string | null
  created_at: string
}

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/watchlist`)
  return data.watchlist
}

export async function addToWatchlist(
  mmsi: number,
  label?: string,
  reason?: string
): Promise<any> {
  const { data } = await axios.post(`${API_URL}/api/v1/watchlist`, { mmsi, label, reason })
  return data
}

export async function removeFromWatchlist(mmsi: number): Promise<void> {
  await axios.delete(`${API_URL}/api/v1/watchlist/${mmsi}`)
}

export async function checkWatched(mmsi: number): Promise<boolean> {
  const { data } = await axios.get(`${API_URL}/api/v1/watchlist/${mmsi}/check`)
  return data.watched
}

export async function fetchSanctions(mmsi: number): Promise<any> {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels/${mmsi}/sanctions`)
  return data
}

export async function fetchEquasis(mmsi: number): Promise<any> {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels/${mmsi}/equasis`)
  return data
}

export function getReportDownloadUrl(mmsi: number): string {
  return `${API_URL}/api/v1/vessels/${mmsi}/report`
}
