import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { useVesselStore, type Vessel } from '../stores/vesselStore'
import { getHighRiskVessels } from './useRisk'
import { fetchSpoofClusters, fetchCorrelationSummary } from './useSpoof'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function fetchVessels(): Promise<Vessel[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels`)
  return data.vessels
}

async function fetchDarkAlerts() {
  const { data } = await axios.get(`${API_URL}/api/v1/alerts/dark-vessels`)
  return data.alerts
}

async function fetchAcousticEvents() {
  try {
    const { data } = await axios.get(`${API_URL}/api/v1/acoustic/events?hours=48`)
    return data.events || []
  } catch {
    return []
  }
}

export function useVessels() {
  const setVessels = useVesselStore((s) => s.setVessels)
  const setDarkAlerts = useVesselStore((s) => s.setDarkAlerts)
  const setCriticalRiskMmsis = useVesselStore((s) => s.setCriticalRiskMmsis)
  const setSpoofClusters = useVesselStore((s) => s.setSpoofClusters)
  const setCorrelationCount = useVesselStore((s) => s.setCorrelationCount)
  const setAcousticEvents = useVesselStore((s) => s.setAcousticEvents)

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

  const spoofQuery = useQuery({
    queryKey: ['spoofClusters'],
    queryFn: () => fetchSpoofClusters('active'),
    refetchInterval: 60000,
  })

  const correlationQuery = useQuery({
    queryKey: ['correlationSummary'],
    queryFn: fetchCorrelationSummary,
    refetchInterval: 60000,
  })

  const acousticQuery = useQuery({
    queryKey: ['acousticEvents'],
    queryFn: fetchAcousticEvents,
    refetchInterval: 120000,
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

  useEffect(() => {
    if (spoofQuery.data) {
      setSpoofClusters(spoofQuery.data)
    }
  }, [spoofQuery.data, setSpoofClusters])

  useEffect(() => {
    if (correlationQuery.data) {
      setCorrelationCount(correlationQuery.data.correlated_pairs)
    }
  }, [correlationQuery.data, setCorrelationCount])

  useEffect(() => {
    if (acousticQuery.data) {
      setAcousticEvents(acousticQuery.data)
    }
  }, [acousticQuery.data, setAcousticEvents])

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

export interface VesselHistory {
  mmsi: number
  first_seen: string | null
  last_seen: string | null
  total_positions: number
  days_active: number
  geographic_spread: string | null
  positions_by_day: { day: string; count: number; bbox: string | null }[]
  identity_changes: {
    name: string | null
    ship_type: string | null
    callsign: string | null
    imo: number | null
    destination: string | null
    observed_at: string | null
  }[]
}

export async function fetchVesselHistory(mmsi: number): Promise<VesselHistory> {
  const { data } = await axios.get(`${API_URL}/api/v1/vessels/${mmsi}/history`)
  return data
}
