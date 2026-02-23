import { useState, useEffect } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { computeRiskScore, getRiskScore, getReportUrl, type RiskScore } from '../../hooks/useRisk'

function RiskBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const barColor = pct >= 75 ? 'bg-red-500' : pct >= 50 ? 'bg-amber-500' : pct >= 25 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-24 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-navy-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-300 w-10 text-right">{score}/{max}</span>
    </div>
  )
}

export default function RiskPanel() {
  const selectedMmsi = useVesselStore((s) => s.selectedMmsi)
  const [risk, setRisk] = useState<RiskScore | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (!selectedMmsi) { setRisk(null); return }
    getRiskScore(selectedMmsi).then(setRisk)
  }, [selectedMmsi])

  const handleCompute = async () => {
    if (!selectedMmsi) return
    setError(null)
    setLoading(true)
    try {
      const res = await computeRiskScore(selectedMmsi)
      setRisk(res)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Risk computation failed')
    } finally {
      setLoading(false)
    }
  }

  if (!selectedMmsi) return null

  const levelColor =
    risk?.risk_level === 'critical' ? 'text-red-400' :
    risk?.risk_level === 'high' ? 'text-amber-400' :
    risk?.risk_level === 'medium' ? 'text-yellow-400' : 'text-green-400'

  return (
    <div className="absolute bottom-72 right-4 w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden z-20">
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="w-full px-3 py-2 bg-red-900/20 border-b border-navy-600 flex justify-between items-center hover:bg-red-900/30 transition-colors"
      >
        <div className="text-left">
          <h3 className="text-red-400 font-semibold text-sm">Risk Assessment</h3>
          <p className="text-[10px] text-gray-500">Scores vessel risk based on identity, flag state, anomalies &amp; dark history</p>
        </div>
        <span className="text-red-400 text-xs ml-2 shrink-0">{isOpen ? '▼' : '▶'}</span>
      </button>

      {isOpen && (
        <>
          <div className="px-3 py-1.5 flex justify-end gap-1">
            <button onClick={handleCompute} disabled={loading}
              className="text-xs bg-red-600 hover:bg-red-500 disabled:bg-red-800 text-white px-2 py-0.5 rounded transition-colors">
              {loading ? '...' : 'Compute'}
            </button>
            <a href={getReportUrl(selectedMmsi)} target="_blank" rel="noreferrer"
              className="text-xs bg-navy-600 hover:bg-navy-500 text-white px-2 py-0.5 rounded transition-colors">
              PDF
            </a>
          </div>

          {error && <p className="px-3 py-1 text-xs text-red-400">{error}</p>}

          {risk && (
            <div className="p-3 pt-0 space-y-2">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-sm font-medium text-white">{risk.vessel_name || `MMSI ${risk.mmsi}`}</div>
                  <div className="text-xs text-gray-400">{risk.ship_type || 'unknown'}</div>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${levelColor}`}>{risk.overall_score}</div>
                  <div className={`text-xs font-medium uppercase ${levelColor}`}>{risk.risk_level}</div>
                </div>
              </div>

              <div className="space-y-1.5 mt-2">
                <RiskBar label="Identity" score={risk.identity_score} max={20} />
                <RiskBar label="Flag State" score={risk.flag_risk_score} max={20} />
                <RiskBar label="Anomalies" score={risk.anomaly_score} max={30} />
                <RiskBar label="Dark History" score={risk.dark_history_score} max={30} />
              </div>

              <div className="text-xs text-gray-500 mt-1">
                Scored: {new Date(risk.scored_at).toLocaleString()}
              </div>
            </div>
          )}

          {!risk && !error && (
            <div className="p-3 pt-0 text-xs text-gray-500">
              No risk score available. Click Compute to assess.
            </div>
          )}
        </>
      )}
    </div>
  )
}
