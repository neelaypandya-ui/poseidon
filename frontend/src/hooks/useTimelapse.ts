import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface TimelapseJob {
  id: number
  status: string
  scene_count: number | null
  composite_type: string
  start_date: string | null
  end_date: string | null
  created_at: string | null
  has_output: boolean
}

export async function createTimelapse(
  bbox: [number, number, number, number],
  startDate: string,
  endDate: string,
  compositeType = 'true-color',
): Promise<number> {
  const { data } = await axios.post(
    `${API_URL}/api/v1/optical/timelapse`,
    null,
    {
      params: {
        min_lon: bbox[0], min_lat: bbox[1],
        max_lon: bbox[2], max_lat: bbox[3],
        start_date: startDate, end_date: endDate,
        composite_type: compositeType,
      },
    },
  )
  return data.job_id
}

export async function getTimelapseStatus(jobId: number): Promise<TimelapseJob> {
  const { data } = await axios.get(`${API_URL}/api/v1/optical/timelapse/${jobId}`)
  return data
}

export function getTimelapseDownloadUrl(jobId: number): string {
  return `${API_URL}/api/v1/optical/timelapse/${jobId}/download`
}

export function useTimelapseJobs() {
  return useQuery({
    queryKey: ['timelapseJobs'],
    queryFn: async () => {
      // This would need a list endpoint; for now return empty
      return [] as TimelapseJob[]
    },
    refetchInterval: 30000,
  })
}
