import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ScheduledReport {
  id: number
  name: string
  report_type: string
  schedule_cron: string
  config: Record<string, any>
  enabled: boolean
  last_run_at: string | null
  created_at: string | null
}

export interface ReportOutput {
  id: number
  report_id: number
  status: string
  has_pdf: boolean
  summary: Record<string, any> | null
  generated_at: string | null
}

async function fetchScheduledReports(): Promise<ScheduledReport[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/reports`)
  return data.reports || []
}

async function fetchReportOutputs(reportId: number): Promise<ReportOutput[]> {
  const { data } = await axios.get(`${API_URL}/api/v1/reports/${reportId}/outputs`)
  return data.outputs || []
}

export function useScheduledReports() {
  return useQuery({
    queryKey: ['scheduledReports'],
    queryFn: fetchScheduledReports,
    refetchInterval: 60000,
  })
}

export function useReportOutputs(reportId: number | null) {
  return useQuery({
    queryKey: ['reportOutputs', reportId],
    queryFn: () => fetchReportOutputs(reportId!),
    enabled: reportId !== null,
  })
}

export function useCreateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { name: string; report_type?: string; cron_expression?: string; config?: Record<string, any> }) => {
      const { data } = await axios.post(`${API_URL}/api/v1/reports`, params)
      return data.report
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduledReports'] }),
  })
}

export function useRunReportNow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (reportId: number) => {
      const { data } = await axios.post(`${API_URL}/api/v1/reports/${reportId}/run`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledReports'] })
      queryClient.invalidateQueries({ queryKey: ['reportOutputs'] })
    },
  })
}

export function useToggleReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (reportId: number) => {
      const { data } = await axios.patch(`${API_URL}/api/v1/reports/${reportId}/toggle`)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduledReports'] }),
  })
}

export function getReportDownloadUrl(outputId: number): string {
  return `${API_URL}/api/v1/reports/outputs/${outputId}/download`
}
