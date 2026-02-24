import { useState } from 'react'
import {
  useScheduledReports,
  useReportOutputs,
  useCreateReport,
  useRunReportNow,
  useToggleReport,
  getReportDownloadUrl,
} from '../../hooks/useScheduledReports'

export default function ScheduledReportsPanel({ isOpen }: { isOpen: boolean }) {
  const [selectedReport, setSelectedReport] = useState<number | null>(null)
  const [newName, setNewName] = useState('')

  const { data: reports } = useScheduledReports()
  const { data: outputs } = useReportOutputs(selectedReport)
  const createReport = useCreateReport()
  const runNow = useRunReportNow()
  const toggleReport = useToggleReport()

  const handleCreate = () => {
    if (!newName.trim()) return
    createReport.mutate({ name: newName, report_type: 'daily_digest', cron_expression: '0 6 * * *', config: { hours_back: 24 } })
    setNewName('')
  }

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-indigo-900/20 border-b border-navy-600">
            <h3 className="text-indigo-400 font-semibold text-sm">Scheduled Reports</h3>
          </div>

          <div className="p-3 space-y-2 border-b border-navy-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New report name..."
                className="flex-1 bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
              <button
                onClick={handleCreate}
                disabled={createReport.isPending}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white text-xs px-2 py-1 rounded transition-colors"
              >
                +
              </button>
            </div>
          </div>

          <div className="max-h-60 overflow-y-auto">
            {reports?.map((r) => (
              <div
                key={r.id}
                className={`px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer ${
                  selectedReport === r.id ? 'bg-navy-700/50' : ''
                }`}
                onClick={() => setSelectedReport(selectedReport === r.id ? null : r.id)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-white truncate">{r.name}</div>
                    <div className="text-xs text-gray-400">
                      {r.schedule_cron} | {r.enabled ? 'Active' : 'Disabled'}
                    </div>
                    {r.last_run_at && (
                      <div className="text-xs text-gray-500">
                        Last: {new Date(r.last_run_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-1 ml-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleReport.mutate(r.id) }}
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        r.enabled ? 'bg-green-800 text-green-300' : 'bg-gray-700 text-gray-400'
                      }`}
                    >
                      {r.enabled ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); runNow.mutate(r.id) }}
                      className="text-xs bg-cyan-800 text-cyan-300 px-1.5 py-0.5 rounded hover:bg-cyan-700"
                    >
                      Run
                    </button>
                  </div>
                </div>

                {selectedReport === r.id && outputs && outputs.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <div className="text-xs text-gray-400 font-medium">History:</div>
                    {outputs.map((o) => (
                      <div key={o.id} className="flex justify-between text-xs">
                        <span className={o.status === 'completed' ? 'text-green-400' : 'text-gray-400'}>
                          {o.generated_at ? new Date(o.generated_at).toLocaleString() : 'Generating...'}
                        </span>
                        {o.has_pdf && (
                          <a
                            href={getReportDownloadUrl(o.id)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-cyan-400 hover:text-cyan-300 underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            PDF
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {(!reports || reports.length === 0) && (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">
                No scheduled reports. Create one above.
              </div>
            )}
          </div>
        </div>
  )
}
