import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ForensicMessage {
  id: number
  mmsi: number
  message_type: string
  raw_json: object
  flag_impossible_speed: boolean
  flag_sart_on_non_sar: boolean
  flag_no_identity: boolean
  flag_position_jump: boolean
  prev_distance_nm: number | null
  implied_speed_knots: number | null
  receiver_class: string
  lat: number | null
  lon: number | null
  sog: number | null
  timestamp: string | null
  received_at: string | null
}

export interface ForensicSummary {
  mmsi: number
  hours: number
  total_messages: number
  flags: {
    impossible_speed: number
    sart_on_non_sar: number
    no_identity: number
    position_jump: number
  }
  receiver_breakdown: {
    terrestrial: number
    terrestrial_pct: number
    satellite: number
    satellite_pct: number
    unknown: number
  }
}

export async function fetchForensicMessages(
  mmsi: number,
  hours = 24,
  flaggedOnly = false,
  limit = 200
): Promise<ForensicMessage[]> {
  const { data } = await axios.get(
    `${API_URL}/api/v1/forensics/messages/${mmsi}?hours=${hours}&flagged_only=${flaggedOnly}&limit=${limit}`
  )
  return data.messages
}

export async function fetchForensicSummary(mmsi: number, hours = 24): Promise<ForensicSummary> {
  const { data } = await axios.get(`${API_URL}/api/v1/forensics/summary/${mmsi}?hours=${hours}`)
  return data
}

export interface AssessmentFinding {
  category: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  detail: string
}

export interface ForensicAssessment {
  mmsi: number
  severity: 'critical' | 'high' | 'medium' | 'low' | 'clean'
  severity_score: number
  verdict: string
  finding_count: number
  findings: AssessmentFinding[]
  vessel_summary: {
    name: string | null
    imo: number | null
    callsign: string | null
    ship_type: string
    has_name: boolean
    has_imo: boolean
    has_callsign: boolean
  }
  track_summary: {
    total_positions: number
    days_active: number
    first_seen: string | null
    last_seen: string | null
  }
  receiver: {
    terrestrial: number
    satellite: number
    terrestrial_pct: number
    satellite_pct: number
  } | null
  identity_changes: number
  active_spoof_signals: number
  active_dark_alerts: number
  assessed_at: string
}

export async function fetchForensicAssessment(mmsi: number): Promise<ForensicAssessment> {
  const { data } = await axios.get(`${API_URL}/api/v1/forensics/assessment/${mmsi}`)
  return data
}
