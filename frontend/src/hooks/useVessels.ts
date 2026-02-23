import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { useVesselStore, type Vessel } from '../stores/vesselStore'
import { getHighRiskVessels } from './useRisk'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function fetchVessels(): Promise<Vessel[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels`)
  return data.vessels
}

async function fetchDarkAlerts() {
  const { data } = await axios.get(`${API_URL}/api/v1/alerts/dark-vessels`)
  return data.alerts
}

export function useVessels() {
  const setVessels = useVesselStore((s) => s.setVessels)
  const setDarkAlerts = useVesselStore((s) => s.setDarkAlerts)
  const setCriticalRiskMmsis = useVesselStore((s) => s.setCriticalRiskMmsis)

  const vesselsQuery = useQuery({
    queryKey: ['vessels'],
    queryFn: fetchVessels,
    refetchInterval: 30000,
  })

  const alertsQuery = useQuery({
    queryKey: ['darkAlerts'],
    queryFn: fetchDarkAlerts,
    refetchInterval: 60000,
  })

  const criticalQuery = useQuery({
    queryKey: ['criticalRiskVessels'],
    queryFn: () => getHighRiskVessels(85),
    refetchInterval: 60000,
  })

  useEffect(() => {
    if (vesselsQuery.data) {
      setVessels(vesselsQuery.data)
    }
  }, [vesselsQuery.data, setVessels])

  useEffect(() => {
    if (alertsQuery.data) {
      setDarkAlerts(alertsQuery.data)
    }
  }, [alertsQuery.data, setDarkAlerts])

  useEffect(() => {
    if (criticalQuery.data) {
      setCriticalRiskMmsis(new Set(criticalQuery.data.map((v) => v.mmsi)))
    }
  }, [criticalQuery.data, setCriticalRiskMmsis])

  return { isLoading: vesselsQuery.isLoading }
}

export async function fetchVesselDetail(mmsi: number) {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels/${mmsi}`)
  return data
}

export async function fetchVesselTrack(mmsi: number, hours = 6) {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels/${mmsi}/track?hours=${hours}`)
  return data.track
}
