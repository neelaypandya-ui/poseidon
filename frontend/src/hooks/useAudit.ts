import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface AuditEntry {
  id: number
  user_id: number | null
  username: string | null
  method: string
  path: string
  status_code: number | null
  client_ip: string | null
  response_time_ms: number | null
  created_at: string
}

export interface AuditStats {
  period_hours: number
  total_requests: number
  unique_users: number
  avg_response_ms: number
  max_response_ms: number
  error_count: number
}

async function fetchAuditLogs(hours = 24, limit = 200): Promise<AuditEntry[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/audit?hours=${hours}&limit=${limit}`)
  return data.entries || []
}

async function fetchAuditStats(hours = 24): Promise<AuditStats> {
  const { data } = await axios.get(`${API_URL}/api/v1/audit/stats?hours=${hours}`)
  return data
}

export function useAuditLogs(hours = 24) {
  return useQuery({
    queryKey: ['auditLogs', hours],
    queryFn: () => fetchAuditLogs(hours),
    refetchInterval: 30000,
  })
}

export function useAuditStats(hours = 24) {
  return useQuery({
    queryKey: ['auditStats', hours],
    queryFn: () => fetchAuditStats(hours),
    refetchInterval: 30000,
  })
}
