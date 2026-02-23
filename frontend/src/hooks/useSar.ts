import axios from 'axios'
import { useVesselStore, type SarScene, type SarDetection } from '../stores/vesselStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function searchSarScenes(
  bbox: [number, number, number, number],
  startDate: string,
  endDate: string,
  limit = 10,
): Promise<SarScene[]> {
  const { data } = await axios.post(`${API_URL}/api/v1/sar/search`, null, {
    params: {
      min_lon: bbox[0],
      min_lat: bbox[1],
      max_lon: bbox[2],
      max_lat: bbox[3],
      start_date: startDate,
      end_date: endDate,
      limit,
    },
  })
  useVesselStore.getState().setSarScenes(data.scenes)
  return data.scenes
}

export async function fetchSarScenes(): Promise<SarScene[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/sar/scenes`)
  useVesselStore.getState().setSarScenes(data.scenes)
  return data.scenes
}

export async function processSarScene(sceneDbId: number): Promise<void> {
  await axios.post(`${API_URL}/api/v1/sar/scenes/${sceneDbId}/process`)
}

export async function fetchSarDetections(
  bbox?: [number, number, number, number],
): Promise<SarDetection[]> {
  const params: Record<string, any> = {}
  if (bbox) {
    params.min_lon = bbox[0]
    params.min_lat = bbox[1]
    params.max_lon = bbox[2]
    params.max_lat = bbox[3]
  }
  const { data } = await axios.get(`${API_URL}/api/v1/sar/detections`, { params })
  useVesselStore.getState().setSarDetections(data.detections)
  return data.detections
}

export async function fetchGhostVessels(
  bbox?: [number, number, number, number],
): Promise<SarDetection[]> {
  const params: Record<string, any> = {}
  if (bbox) {
    params.min_lon = bbox[0]
    params.min_lat = bbox[1]
    params.max_lon = bbox[2]
    params.max_lat = bbox[3]
  }
  const { data } = await axios.get(`${API_URL}/api/v1/sar/ghost-vessels`, { params })
  return data.ghost_vessels
}
