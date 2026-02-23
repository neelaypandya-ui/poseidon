import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ReplayFrame {
  timestamp: string
  vessels: {
    mmsi: number
    lon: number
    lat: number
    sog: number
    cog: number
  }[]
}

export interface ReplayData {
  job_id: number
  frames: ReplayFrame[]
  total_frames: number
  start_time: string
  end_time: string
  speed: number
}

export async function createReplayJob(params: {
  mmsi?: number
  min_lon?: number
  min_lat?: number
  max_lon?: number
  max_lat?: number
  start_time: string
  end_time: string
  speed?: number
}): Promise<number> {
  const { data } = await axios.post(`${API_URL}/api/v1/replay/create`, null, { params })
  return data.job_id
}

export async function getReplayData(jobId: number): Promise<ReplayData> {
  const { data } = await axios.get(`${API_URL}/api/v1/replay/${jobId}/data`)
  return data
}

export async function getReplayStatus(jobId: number) {
  const { data } = await axios.get(`${API_URL}/api/v1/replay/${jobId}`)
  return data
}
