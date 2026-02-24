import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface AcousticEvent {
  id: number
  source: string
  event_type: string
  lon: number | null
  lat: number | null
  bearing: number | null
  magnitude: number | null
  event_time: string
  correlated_mmsi: number | null
  correlation_confidence: number | null
}

async function fetchAcousticEvents(hours = 48): Promise<AcousticEvent[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/acoustic/events?hours=${hours}`)
  return data.events || []
}

export async function triggerAcousticFetch() {
  const { data } = await axios.post(`${API_URL}/api/v1/acoustic/fetch`)
  return data
}

export async function correlateAcousticEvent(eventId: number) {
  const { data } = await axios.post(`${API_URL}/api/v1/acoustic/correlate/${eventId}`)
  return data
}

export function useAcousticEvents(hours = 48) {
  return useQuery({
    queryKey: ['acousticEvents', hours],
    queryFn: () => fetchAcousticEvents(hours),
    refetchInterval: 120000,
  })
}
