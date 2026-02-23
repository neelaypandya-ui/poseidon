import axios from 'axios'
import { useVesselStore, type OpticalScene } from '../stores/vesselStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function searchOpticalScenes(
  bbox: [number, number, number, number],
  startDate: string,
  endDate: string,
  maxCloud = 30,
  limit = 20,
): Promise<OpticalScene[]> {
  const { data } = await axios.post(`${API_URL}/api/v1/optical/search`, null, {
    params: {
      min_lon: bbox[0],
      min_lat: bbox[1],
      max_lon: bbox[2],
      max_lat: bbox[3],
      start_date: startDate,
      end_date: endDate,
      max_cloud: maxCloud,
      limit,
    },
  })
  useVesselStore.getState().setOpticalScenes(data.scenes)
  return data.scenes
}

export async function fetchOpticalScenes(): Promise<OpticalScene[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/optical/scenes`)
  useVesselStore.getState().setOpticalScenes(data.scenes)
  return data.scenes
}

export async function downloadOpticalScene(sceneDbId: number): Promise<void> {
  await axios.post(`${API_URL}/api/v1/optical/scenes/${sceneDbId}/download`)
}

export async function createTimelapse(
  bbox: [number, number, number, number],
  startDate: string,
  endDate: string,
): Promise<number> {
  const { data } = await axios.post(`${API_URL}/api/v1/optical/timelapse`, null, {
    params: {
      min_lon: bbox[0],
      min_lat: bbox[1],
      max_lon: bbox[2],
      max_lat: bbox[3],
      start_date: startDate,
      end_date: endDate,
    },
  })
  return data.job_id
}

export async function getTimelapseStatus(jobId: number) {
  const { data } = await axios.get(`${API_URL}/api/v1/optical/timelapse/${jobId}`)
  return data
}

export function getTimelapseDownloadUrl(jobId: number): string {
  return `${API_URL}/api/v1/optical/timelapse/${jobId}/download`
}
