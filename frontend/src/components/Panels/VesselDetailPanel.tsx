import { useEffect, useMemo, useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchVesselDetail, fetchVesselHistory, type VesselHistory } from '../../hooks/useVessels'
import { predictRoute } from '../../hooks/useRoutes'
import { getFlagFromMmsi } from '../../utils/flags'
import { computeRiskScore, getRiskScore, getReportUrl, type RiskScore } from '../../hooks/useRisk'
import { computeFusion, getFusionHistory, type FusionResult } from '../../hooks/useFusion'
import { fetchForensicMessages, fetchForensicSummary, fetchForensicAssessment, type ForensicMessage, type ForensicSummary, type ForensicAssessment } from '../../hooks/useForensics'
import { addToWatchlist, checkWatched, removeFromWatchlist, fetchSanctions, fetchEquasis, getReportDownloadUrl } from '../../hooks/useWatchlist'

interface VesselDetail {
  mmsi: number
  imo: number | null
  name: string | null
  callsign: string | null
  ship_type: string
  destination: string | null
  lon: number | null
  lat: number | null
  sog: number | null
  cog: number | null
  heading: number | null
  nav_status: string | null
  last_seen: string | null
  track_points_6h: number
  dim_bow: number | null
  dim_stern: number | null
  dim_port: number | null
  dim_starboard: number | null
}

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

function ConfidenceBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-navy-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${(value * 100).toFixed(0)}%` }} />
      </div>
      <span className="text-xs text-gray-300 w-10 text-right">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

export default function VesselDetailPanel() {
  const selectedMmsi = useVesselStore((s) => s.selectedMmsi)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)
  const setForensicPings = useVesselStore((s) => s.setForensicPings)
  const [detail, setDetail] = useState<VesselDetail | null>(null)
  const [loading, setLoading] = useState(false)

  // Risk state
  const [risk, setRisk] = useState<RiskScore | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)
  const [riskOpen, setRiskOpen] = useState(false)

  // Fusion state
  const [fusion, setFusion] = useState<FusionResult | null>(null)
  const [fusionHistory, setFusionHistory] = useState<FusionResult[]>([])
  const [fusionLoading, setFusionLoading] = useState(false)
  const [fusionError, setFusionError] = useState<string | null>(null)
  const [fusionOpen, setFusionOpen] = useState(false)

  // History state
  const [history, setHistory] = useState<VesselHistory | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  // Assessment state
  const [assessment, setAssessment] = useState<ForensicAssessment | null>(null)
  const [assessmentLoading, setAssessmentLoading] = useState(false)

  // Watchlist state
  const [isWatched, setIsWatched] = useState(false)
  const [watchlistLoading, setWatchlistLoading] = useState(false)

  // Sanctions state
  const [sanctions, setSanctions] = useState<any>(null)
  const [sanctionsLoading, setSanctionsLoading] = useState(false)
  const [sanctionsOpen, setSanctionsOpen] = useState(false)

  // Equasis state
  const [equasis, setEquasis] = useState<any>(null)
  const [equasisLoading, setEquasisLoading] = useState(false)
  const [equasisOpen, setEquasisOpen] = useState(false)

  // Forensics state
  const [forensicSummary, setForensicSummary] = useState<ForensicSummary | null>(null)
  const [forensicMessages, setForensicMessages] = useState<ForensicMessage[]>([])
  const [forensicsLoading, setForensicsLoading] = useState(false)
  const [forensicsOpen, setForensicsOpen] = useState(false)
  const [expandedMsgId, setExpandedMsgId] = useState<number | null>(null)

  useEffect(() => {
    if (!selectedMmsi) {
      setDetail(null)
      setRisk(null)
      setFusion(null)
      setFusionHistory([])
      setRiskOpen(false)
      setFusionOpen(false)
      setAssessment(null)
      setHistory(null)
      setHistoryOpen(false)
      setForensicSummary(null)
      setForensicMessages([])
      setForensicsOpen(false)
      setExpandedMsgId(null)
      setIsWatched(false)
      setSanctions(null)
      setSanctionsOpen(false)
      setEquasis(null)
      setEquasisOpen(false)
      setForensicPings([])
      return
    }
    setLoading(true)
    setAssessmentLoading(true)
    fetchVesselDetail(selectedMmsi)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
    getRiskScore(selectedMmsi).then(setRisk)
    fetchForensicAssessment(selectedMmsi)
      .then(setAssessment)
      .catch(() => setAssessment(null))
      .finally(() => setAssessmentLoading(false))
    checkWatched(selectedMmsi).then(setIsWatched).catch(() => setIsWatched(false))
  }, [selectedMmsi])

  const flagInfo = useMemo(
    () => (selectedMmsi ? getFlagFromMmsi(selectedMmsi) : null),
    [selectedMmsi],
  )

  const handleComputeRisk = async () => {
    if (!selectedMmsi) return
    setRiskError(null)
    setRiskLoading(true)
    try {
      const res = await computeRiskScore(selectedMmsi)
      setRisk(res)
    } catch (e: any) {
      setRiskError(e?.response?.data?.detail || 'Risk computation failed')
    } finally {
      setRiskLoading(false)
    }
  }

  const handleComputeFusion = async () => {
    if (!selectedMmsi) return
    setFusionError(null)
    setFusionLoading(true)
    try {
      const res = await computeFusion(selectedMmsi)
      setFusion(res)
      const hist = await getFusionHistory(selectedMmsi, 10)
      setFusionHistory(hist)
    } catch (e: any) {
      setFusionError(e?.response?.data?.detail || 'Fusion computation failed')
    } finally {
      setFusionLoading(false)
    }
  }

  if (!selectedMmsi) return null

  const levelColor =
    risk?.risk_level === 'critical' ? 'text-red-400' :
    risk?.risk_level === 'high' ? 'text-amber-400' :
    risk?.risk_level === 'medium' ? 'text-yellow-400' : 'text-green-400'

  const posteriorColor = fusion
    ? fusion.posterior_score >= 0.8 ? 'text-green-400'
    : fusion.posterior_score >= 0.5 ? 'text-cyan-400'
    : fusion.posterior_score >= 0.3 ? 'text-yellow-400'
    : 'text-red-400'
    : ''

  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-navy-800/95 backdrop-blur border-l border-navy-600 overflow-y-auto z-20">
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-cyan-400">Vessel Detail</h2>
          <button
            onClick={() => {
              setSelectedMmsi(null)
              setSelectedTrack([])
            }}
            className="text-gray-400 hover:text-white text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {loading && <p className="text-gray-400 text-sm">Loading...</p>}

        {detail && (
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-gray-400">Name</div>
              <div className="font-medium flex items-center gap-2">
                {flagInfo && <img src={flagInfo.flagUrl} alt={flagInfo.country} title={flagInfo.country} className="h-4 inline-block" />}
                {detail.name || 'Unknown'}
              </div>
            </div>
            {flagInfo && (
              <div>
                <div className="text-gray-400">Flag State</div>
                <div className="flex items-center gap-2">
                  <img src={flagInfo.flagUrl} alt={flagInfo.country} className="h-4 inline-block" />
                  {flagInfo.country}
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-400">MMSI</div>
                <div className="font-mono">{detail.mmsi}</div>
              </div>
              <div>
                <div className="text-gray-400">IMO</div>
                <div className="font-mono">{detail.imo || '—'}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-400">Type</div>
                <div className="capitalize">{detail.ship_type}</div>
              </div>
              <div>
                <div className="text-gray-400">Callsign</div>
                <div className="font-mono">{detail.callsign || '—'}</div>
              </div>
            </div>

            <hr className="border-navy-600" />

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-400">Speed (SOG)</div>
                <div>{detail.sog != null ? `${detail.sog.toFixed(1)} kn` : '—'}</div>
              </div>
              <div>
                <div className="text-gray-400">Course (COG)</div>
                <div>{detail.cog != null ? `${detail.cog.toFixed(1)}°` : '—'}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-400">Heading</div>
                <div>{detail.heading != null ? `${detail.heading}°` : '—'}</div>
              </div>
              <div>
                <div className="text-gray-400">Nav Status</div>
                <div className="text-xs">{detail.nav_status?.replace(/_/g, ' ') || '—'}</div>
              </div>
            </div>

            <hr className="border-navy-600" />

            <div>
              <div className="text-gray-400">Destination</div>
              <div>{detail.destination || '—'}</div>
            </div>
            <div>
              <div className="text-gray-400">Position</div>
              <div className="font-mono text-xs">
                {detail.lat != null && detail.lon != null
                  ? `${detail.lat.toFixed(5)}, ${detail.lon.toFixed(5)}`
                  : '—'}
              </div>
            </div>

            {(detail.dim_bow || detail.dim_stern) && (
              <div>
                <div className="text-gray-400">Dimensions</div>
                <div className="text-xs">
                  {(detail.dim_bow || 0) + (detail.dim_stern || 0)}m ×{' '}
                  {(detail.dim_port || 0) + (detail.dim_starboard || 0)}m
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-400">Track (6h)</div>
                <div>{detail.track_points_6h} points</div>
              </div>
              <div>
                <div className="text-gray-400">Last Seen</div>
                <div className="text-xs">
                  {detail.last_seen
                    ? new Date(detail.last_seen).toLocaleTimeString()
                    : '—'}
                </div>
              </div>
            </div>

            <hr className="border-navy-600" />

            <button
              onClick={() => detail && predictRoute(detail.mmsi, 24)}
              className="w-full bg-green-600 hover:bg-green-500 text-white text-sm font-medium py-1.5 rounded transition-colors"
            >
              Predict Route (24h)
            </button>

            <div className="flex gap-2">
              <button
                onClick={async () => {
                  if (!selectedMmsi) return
                  setWatchlistLoading(true)
                  try {
                    if (isWatched) {
                      await removeFromWatchlist(selectedMmsi)
                      setIsWatched(false)
                    } else {
                      await addToWatchlist(selectedMmsi)
                      setIsWatched(true)
                    }
                  } finally {
                    setWatchlistLoading(false)
                  }
                }}
                disabled={watchlistLoading}
                className={`flex-1 text-sm font-medium py-1.5 rounded transition-colors ${
                  isWatched
                    ? 'bg-indigo-700 hover:bg-indigo-600 text-white'
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                } disabled:opacity-50`}
              >
                {watchlistLoading ? '...' : isWatched ? 'Unwatchlist' : 'Add to Watchlist'}
              </button>
              <a
                href={getReportDownloadUrl(selectedMmsi)}
                target="_blank"
                rel="noreferrer"
                className="flex-1 text-sm font-medium py-1.5 rounded bg-navy-600 hover:bg-navy-500 text-white text-center transition-colors"
              >
                Export PDF
              </a>
            </div>
          </div>
        )}

        {/* Signal Assessment */}
        {detail && (assessment || assessmentLoading) && (
          <div className="mt-4 border border-navy-600 rounded-lg overflow-hidden">
            <div className={`px-3 py-2 ${
              assessment?.severity === 'critical' ? 'bg-red-900/30' :
              assessment?.severity === 'high' ? 'bg-orange-900/30' :
              assessment?.severity === 'medium' ? 'bg-yellow-900/30' :
              assessment?.severity === 'low' ? 'bg-blue-900/20' :
              'bg-green-900/20'
            }`}>
              <div className="flex justify-between items-center">
                <h3 className={`font-semibold text-sm ${
                  assessment?.severity === 'critical' ? 'text-red-400' :
                  assessment?.severity === 'high' ? 'text-orange-400' :
                  assessment?.severity === 'medium' ? 'text-yellow-400' :
                  assessment?.severity === 'low' ? 'text-blue-400' :
                  'text-green-400'
                }`}>
                  Signal Assessment
                </h3>
                {assessment && (
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${
                      assessment.severity === 'critical' ? 'text-red-400' :
                      assessment.severity === 'high' ? 'text-orange-400' :
                      assessment.severity === 'medium' ? 'text-yellow-400' :
                      assessment.severity === 'low' ? 'text-blue-400' :
                      'text-green-400'
                    }`}>
                      {assessment.severity_score}
                    </span>
                    <span className={`text-[10px] font-medium uppercase px-1.5 py-0.5 rounded ${
                      assessment.severity === 'critical' ? 'bg-red-500/30 text-red-300' :
                      assessment.severity === 'high' ? 'bg-orange-500/30 text-orange-300' :
                      assessment.severity === 'medium' ? 'bg-yellow-500/30 text-yellow-300' :
                      assessment.severity === 'low' ? 'bg-blue-500/30 text-blue-300' :
                      'bg-green-500/30 text-green-300'
                    }`}>
                      {assessment.severity}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {assessmentLoading && (
              <div className="px-3 py-2 text-xs text-gray-400">Analyzing...</div>
            )}

            {assessment && (
              <div className="p-3 space-y-2">
                {/* Verdict */}
                <p className="text-xs text-gray-300 italic">{assessment.verdict}</p>

                {/* Score bar */}
                <div className="h-1.5 bg-navy-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      assessment.severity === 'critical' ? 'bg-red-500' :
                      assessment.severity === 'high' ? 'bg-orange-500' :
                      assessment.severity === 'medium' ? 'bg-yellow-500' :
                      assessment.severity === 'low' ? 'bg-blue-500' :
                      'bg-green-500'
                    }`}
                    style={{ width: `${assessment.severity_score}%` }}
                  />
                </div>

                {/* Quick stats row */}
                <div className="flex gap-2 text-[10px]">
                  <span className="text-gray-500">
                    {assessment.track_summary.total_positions.toLocaleString()} pos
                  </span>
                  <span className="text-gray-600">|</span>
                  <span className="text-gray-500">
                    {assessment.track_summary.days_active}d active
                  </span>
                  {assessment.receiver && (
                    <>
                      <span className="text-gray-600">|</span>
                      <span className="text-green-500">{assessment.receiver.terrestrial_pct}% terr</span>
                      <span className="text-blue-400">{assessment.receiver.satellite_pct}% sat</span>
                    </>
                  )}
                </div>

                {/* Findings */}
                {assessment.findings.length > 0 && (
                  <div className="space-y-1.5">
                    {assessment.findings.map((f, i) => (
                      <div
                        key={i}
                        className={`rounded px-2 py-1.5 text-xs border-l-2 ${
                          f.severity === 'critical' ? 'bg-red-900/20 border-red-500' :
                          f.severity === 'high' ? 'bg-orange-900/20 border-orange-500' :
                          f.severity === 'medium' ? 'bg-yellow-900/20 border-yellow-500' :
                          'bg-blue-900/20 border-blue-500'
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[9px] font-medium uppercase px-1 py-0.5 rounded ${
                            f.severity === 'critical' ? 'bg-red-500/30 text-red-300' :
                            f.severity === 'high' ? 'bg-orange-500/30 text-orange-300' :
                            f.severity === 'medium' ? 'bg-yellow-500/30 text-yellow-300' :
                            'bg-blue-500/30 text-blue-300'
                          }`}>
                            {f.severity}
                          </span>
                          <span className="font-medium text-gray-200">{f.title}</span>
                        </div>
                        <p className="text-gray-400 mt-0.5 leading-snug">{f.detail}</p>
                      </div>
                    ))}
                  </div>
                )}

                {assessment.findings.length === 0 && (
                  <div className="text-xs text-green-400/80 text-center py-1">
                    No anomalies detected
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Risk Assessment Section */}
        {detail && (
          <div className="mt-4 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => setRiskOpen((o) => !o)}
              className="w-full px-3 py-2 bg-red-900/20 flex justify-between items-center hover:bg-red-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-red-400 font-semibold text-sm">Risk Assessment</h3>
                <p className="text-[10px] text-gray-500">Identity, flag state, anomalies &amp; dark history scoring</p>
              </div>
              <span className="text-red-400 text-xs ml-2 shrink-0">{riskOpen ? '▼' : '▶'}</span>
            </button>

            {riskOpen && (
              <div className="border-t border-navy-600">
                <div className="px-3 py-1.5 flex justify-end gap-1">
                  <button onClick={handleComputeRisk} disabled={riskLoading}
                    className="text-xs bg-red-600 hover:bg-red-500 disabled:bg-red-800 text-white px-2 py-0.5 rounded transition-colors">
                    {riskLoading ? '...' : 'Compute'}
                  </button>
                  <a href={getReportUrl(selectedMmsi)} target="_blank" rel="noreferrer"
                    className="text-xs bg-navy-600 hover:bg-navy-500 text-white px-2 py-0.5 rounded transition-colors">
                    PDF
                  </a>
                </div>

                {riskError && <p className="px-3 py-1 text-xs text-red-400">{riskError}</p>}

                {risk && (
                  <div className="p-3 pt-0 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-gray-400">{risk.ship_type || 'unknown'}</span>
                      <div className="text-right">
                        <span className={`text-xl font-bold ${levelColor}`}>{risk.overall_score}</span>
                        <span className={`text-xs font-medium uppercase ${levelColor} ml-1`}>{risk.risk_level}</span>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <RiskBar label="Identity" score={risk.identity_score} max={20} />
                      <RiskBar label="Flag State" score={risk.flag_risk_score} max={20} />
                      <RiskBar label="Anomalies" score={risk.anomaly_score} max={30} />
                      <RiskBar label="Dark History" score={risk.dark_history_score} max={30} />
                    </div>
                    <div className="text-xs text-gray-500">
                      Scored: {new Date(risk.scored_at).toLocaleString()}
                    </div>
                  </div>
                )}

                {!risk && !riskError && (
                  <div className="px-3 pb-2 text-xs text-gray-500">
                    No risk score yet. Click Compute to assess.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Signal Fusion Section */}
        {detail && (
          <div className="mt-3 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => setFusionOpen((o) => !o)}
              className="w-full px-3 py-2 bg-cyan-900/20 flex justify-between items-center hover:bg-cyan-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-cyan-400 font-semibold text-sm">Signal Fusion</h3>
                <p className="text-[10px] text-gray-500">Combines AIS, SAR, VIIRS &amp; acoustic into one confidence score</p>
              </div>
              <span className="text-cyan-400 text-xs ml-2 shrink-0">{fusionOpen ? '▼' : '▶'}</span>
            </button>

            {fusionOpen && (
              <div className="border-t border-navy-600">
                <div className="px-3 py-1.5 flex justify-end">
                  <button
                    onClick={handleComputeFusion}
                    disabled={fusionLoading}
                    className="text-xs bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white px-2 py-0.5 rounded transition-colors"
                  >
                    {fusionLoading ? 'Computing...' : 'Compute'}
                  </button>
                </div>

                {fusionError && <p className="px-3 py-1 text-xs text-red-400">{fusionError}</p>}

                {fusion && (
                  <div className="p-3 pt-0 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-gray-400">MMSI {fusion.mmsi}</span>
                      <span className={`text-sm font-bold ${posteriorColor}`}>
                        {(fusion.posterior_score * 100).toFixed(0)}% {fusion.classification}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <ConfidenceBar label="AIS" value={fusion.ais_confidence} color="bg-cyan-500" />
                      <ConfidenceBar label="SAR" value={fusion.sar_confidence} color="bg-amber-500" />
                      <ConfidenceBar label="VIIRS" value={fusion.viirs_confidence} color="bg-orange-500" />
                      <ConfidenceBar label="Acoustic" value={fusion.acoustic_confidence} color="bg-purple-500" />
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(fusion.timestamp).toLocaleString()}
                    </div>
                  </div>
                )}

                {fusionHistory.length > 1 && (
                  <div className="px-3 pb-2">
                    <div className="text-xs text-gray-500 mb-1">History ({fusionHistory.length})</div>
                    <div className="flex gap-0.5 h-8 items-end">
                      {fusionHistory.slice().reverse().map((h, i) => (
                        <div
                          key={h.id || i}
                          className="flex-1 bg-cyan-600/60 rounded-t"
                          style={{ height: `${h.posterior_score * 100}%` }}
                          title={`${(h.posterior_score * 100).toFixed(0)}% - ${new Date(h.timestamp).toLocaleDateString()}`}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* History Section */}
        {detail && (
          <div className="mt-3 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => {
                const opening = !historyOpen
                setHistoryOpen(opening)
                if (opening && !history && selectedMmsi) {
                  setHistoryLoading(true)
                  fetchVesselHistory(selectedMmsi)
                    .then(setHistory)
                    .catch(() => setHistory(null))
                    .finally(() => setHistoryLoading(false))
                }
              }}
              className="w-full px-3 py-2 bg-blue-900/20 flex justify-between items-center hover:bg-blue-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-blue-400 font-semibold text-sm">History</h3>
                <p className="text-[10px] text-gray-500">When &amp; where this MMSI has appeared</p>
              </div>
              <span className="text-blue-400 text-xs ml-2 shrink-0">{historyOpen ? '▼' : '▶'}</span>
            </button>

            {historyOpen && (
              <div className="border-t border-navy-600 p-3 space-y-2">
                {historyLoading && <p className="text-xs text-gray-400">Loading...</p>}
                {history && (
                  <>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-gray-400">First seen</span>
                        <div>{history.first_seen ? new Date(history.first_seen).toLocaleDateString() : '—'}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Last seen</span>
                        <div>{history.last_seen ? new Date(history.last_seen).toLocaleDateString() : '—'}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Total positions</span>
                        <div>{history.total_positions.toLocaleString()}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Days active</span>
                        <div>{history.days_active}</div>
                      </div>
                    </div>

                    {history.positions_by_day.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Daily positions (90d)</div>
                        <div className="flex gap-px h-8 items-end">
                          {history.positions_by_day.slice(0, 90).reverse().map((d) => {
                            const maxCount = Math.max(...history.positions_by_day.map((p) => p.count))
                            const pct = maxCount > 0 ? (d.count / maxCount) * 100 : 0
                            return (
                              <div
                                key={d.day}
                                className="flex-1 bg-blue-500/60 rounded-t min-w-[2px]"
                                style={{ height: `${Math.max(pct, 4)}%` }}
                                title={`${d.day}: ${d.count} positions`}
                              />
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {history.identity_changes.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Identity changes ({history.identity_changes.length})</div>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {history.identity_changes.map((c, i) => (
                            <div key={i} className="text-xs bg-navy-700/50 rounded px-2 py-1">
                              <div className="flex justify-between">
                                <span className="text-blue-300">{c.name || '(no name)'}</span>
                                <span className="text-gray-500">{c.observed_at ? new Date(c.observed_at).toLocaleDateString() : ''}</span>
                              </div>
                              <div className="text-gray-500">
                                {[c.ship_type, c.callsign, c.imo ? `IMO ${c.imo}` : null].filter(Boolean).join(' | ')}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {history.geographic_spread && (
                      <div className="text-xs text-gray-500">
                        Bbox: {history.geographic_spread}
                      </div>
                    )}
                  </>
                )}
                {!history && !historyLoading && (
                  <p className="text-xs text-gray-500">No history data available.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Message Forensics Section */}
        {detail && (
          <div className="mt-3 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => {
                const opening = !forensicsOpen
                setForensicsOpen(opening)
                if (opening && !forensicSummary && selectedMmsi) {
                  setForensicsLoading(true)
                  Promise.all([
                    fetchForensicSummary(selectedMmsi),
                    fetchForensicMessages(selectedMmsi, 24, false, 50),
                  ])
                    .then(([summary, msgs]) => {
                      setForensicSummary(summary)
                      setForensicMessages(msgs)
                      // Push forensic pings to map
                      const pings = msgs
                        .filter((m) => m.lat != null && m.lon != null)
                        .map((m) => ({
                          id: m.id,
                          lon: m.lon!,
                          lat: m.lat!,
                          flagged: m.flag_impossible_speed || m.flag_sart_on_non_sar || m.flag_no_identity || m.flag_position_jump,
                          timestamp: m.timestamp || m.received_at || '',
                        }))
                      setForensicPings(pings)
                    })
                    .catch(() => {
                      setForensicSummary(null)
                      setForensicMessages([])
                      setForensicPings([])
                    })
                    .finally(() => setForensicsLoading(false))
                }
              }}
              className="w-full px-3 py-2 bg-amber-900/20 flex justify-between items-center hover:bg-amber-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-amber-400 font-semibold text-sm">Message Forensics</h3>
                <p className="text-[10px] text-gray-500">Raw messages, flags &amp; receiver classification</p>
              </div>
              <span className="text-amber-400 text-xs ml-2 shrink-0">{forensicsOpen ? '▼' : '▶'}</span>
            </button>

            {forensicsOpen && (
              <div className="border-t border-navy-600 p-3 space-y-2">
                {forensicsLoading && <p className="text-xs text-gray-400">Loading...</p>}
                {forensicSummary && (
                  <>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-gray-400">{forensicSummary.total_messages} messages (24h)</span>
                      {forensicSummary.flags.impossible_speed > 0 && (
                        <span className="bg-red-500/80 text-white px-1.5 py-0.5 rounded-full text-[9px]">
                          {forensicSummary.flags.impossible_speed} speed
                        </span>
                      )}
                      {forensicSummary.flags.sart_on_non_sar > 0 && (
                        <span className="bg-amber-500/80 text-white px-1.5 py-0.5 rounded-full text-[9px]">
                          {forensicSummary.flags.sart_on_non_sar} SART
                        </span>
                      )}
                      {forensicSummary.flags.no_identity > 0 && (
                        <span className="bg-yellow-500/80 text-white px-1.5 py-0.5 rounded-full text-[9px]">
                          {forensicSummary.flags.no_identity} no-ID
                        </span>
                      )}
                      {forensicSummary.flags.position_jump > 0 && (
                        <span className="bg-orange-500/80 text-white px-1.5 py-0.5 rounded-full text-[9px]">
                          {forensicSummary.flags.position_jump} jump
                        </span>
                      )}
                    </div>

                    <div className="text-xs">
                      <span className="text-gray-400">Receiver: </span>
                      <span className="text-green-400">
                        Terrestrial {forensicSummary.receiver_breakdown.terrestrial_pct}%
                      </span>
                      <span className="text-gray-600 mx-1">|</span>
                      <span className="text-blue-400">
                        Satellite {forensicSummary.receiver_breakdown.satellite_pct}%
                      </span>
                    </div>
                  </>
                )}

                {forensicMessages.length > 0 && (
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {forensicMessages.map((msg) => {
                      const hasFlag = msg.flag_impossible_speed || msg.flag_sart_on_non_sar || msg.flag_no_identity || msg.flag_position_jump
                      return (
                        <div
                          key={msg.id}
                          className={`text-xs rounded px-2 py-1 cursor-pointer ${hasFlag ? 'bg-amber-900/30 border border-amber-800/50' : 'bg-navy-700/50'}`}
                          onClick={() => setExpandedMsgId(expandedMsgId === msg.id ? null : msg.id)}
                        >
                          <div className="flex justify-between items-center">
                            <div className="flex items-center gap-1">
                              <span className="text-gray-300">{msg.message_type}</span>
                              {msg.flag_impossible_speed && <span className="w-2 h-2 rounded-full bg-red-500 inline-block" title="Impossible speed" />}
                              {msg.flag_sart_on_non_sar && <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" title="SART on non-SAR" />}
                              {msg.flag_no_identity && <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" title="No identity" />}
                              {msg.flag_position_jump && <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" title="Position jump" />}
                            </div>
                            <span className="text-gray-500 text-[10px]">
                              {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                            </span>
                          </div>
                          <div className="text-gray-500">
                            {msg.receiver_class}
                            {msg.sog != null && ` | ${msg.sog.toFixed(1)} kn`}
                            {msg.lat != null && msg.lon != null && ` | ${msg.lat.toFixed(3)}, ${msg.lon.toFixed(3)}`}
                          </div>
                          {expandedMsgId === msg.id && (
                            <pre className="mt-1 text-[10px] text-gray-500 bg-navy-900/50 rounded p-1 overflow-x-auto max-h-32 whitespace-pre-wrap">
                              {JSON.stringify(msg.raw_json, null, 2)}
                            </pre>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {!forensicSummary && !forensicsLoading && (
                  <p className="text-xs text-gray-500">No forensic data available.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Sanctions Screening Section */}
        {detail && (
          <div className="mt-3 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => {
                const opening = !sanctionsOpen
                setSanctionsOpen(opening)
                if (opening && !sanctions && selectedMmsi) {
                  setSanctionsLoading(true)
                  fetchSanctions(selectedMmsi)
                    .then(setSanctions)
                    .catch(() => setSanctions(null))
                    .finally(() => setSanctionsLoading(false))
                }
              }}
              className="w-full px-3 py-2 bg-rose-900/20 flex justify-between items-center hover:bg-rose-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-rose-400 font-semibold text-sm">Sanctions Screening</h3>
                <p className="text-[10px] text-gray-500">OpenSanctions database check</p>
              </div>
              <span className="text-rose-400 text-xs ml-2 shrink-0">{sanctionsOpen ? '▼' : '▶'}</span>
            </button>

            {sanctionsOpen && (
              <div className="border-t border-navy-600 p-3 space-y-2">
                {sanctionsLoading && <p className="text-xs text-gray-400">Screening...</p>}
                {sanctions && (
                  <>
                    {sanctions.matches && sanctions.matches.length > 0 ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-red-400 bg-red-500/20 px-2 py-0.5 rounded">
                            {sanctions.matches.length} MATCH{sanctions.matches.length > 1 ? 'ES' : ''}
                          </span>
                        </div>
                        {sanctions.matches.map((m: any, i: number) => (
                          <div key={i} className="bg-red-900/20 rounded p-2 text-xs border border-red-800/30">
                            <div className="font-medium text-red-300">{m.matched_name || m.entity_name}</div>
                            <div className="text-gray-400 mt-0.5">
                              {m.sanction_programs && <span>Programs: {m.sanction_programs}</span>}
                            </div>
                            {m.score && (
                              <div className="text-gray-500 mt-0.5">Match score: {(m.score * 100).toFixed(0)}%</div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-green-400/80 text-center py-1">
                        No sanctions matches found
                      </div>
                    )}
                    {sanctions.screened_at && (
                      <div className="text-[10px] text-gray-500">
                        Screened: {new Date(sanctions.screened_at).toLocaleString()}
                      </div>
                    )}
                  </>
                )}
                {!sanctions && !sanctionsLoading && (
                  <p className="text-xs text-gray-500">Click to screen against sanctions databases.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Equasis Vessel Registry Section */}
        {detail && (
          <div className="mt-3 border border-navy-600 rounded-lg overflow-hidden">
            <button
              onClick={() => {
                const opening = !equasisOpen
                setEquasisOpen(opening)
                if (opening && !equasis && selectedMmsi) {
                  setEquasisLoading(true)
                  fetchEquasis(selectedMmsi)
                    .then(setEquasis)
                    .catch(() => setEquasis(null))
                    .finally(() => setEquasisLoading(false))
                }
              }}
              className="w-full px-3 py-2 bg-violet-900/20 flex justify-between items-center hover:bg-violet-900/30 transition-colors"
            >
              <div className="text-left">
                <h3 className="text-violet-400 font-semibold text-sm">Vessel Registry</h3>
                <p className="text-[10px] text-gray-500">Equasis ownership &amp; inspection data</p>
              </div>
              <span className="text-violet-400 text-xs ml-2 shrink-0">{equasisOpen ? '▼' : '▶'}</span>
            </button>

            {equasisOpen && (
              <div className="border-t border-navy-600 p-3 space-y-2">
                {equasisLoading && <p className="text-xs text-gray-400">Looking up registry...</p>}
                {equasis && equasis.data && (
                  <>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {equasis.data.vessel_name && (
                        <div>
                          <span className="text-gray-400">Name</span>
                          <div className="text-violet-300">{equasis.data.vessel_name}</div>
                        </div>
                      )}
                      {equasis.data.flag_state && (
                        <div>
                          <span className="text-gray-400">Flag</span>
                          <div>{equasis.data.flag_state}</div>
                        </div>
                      )}
                      {equasis.data.registered_owner && (
                        <div className="col-span-2">
                          <span className="text-gray-400">Owner</span>
                          <div className="text-violet-300">{equasis.data.registered_owner}</div>
                        </div>
                      )}
                      {equasis.data.operator && (
                        <div className="col-span-2">
                          <span className="text-gray-400">Operator</span>
                          <div>{equasis.data.operator}</div>
                        </div>
                      )}
                      {equasis.data.class_society && (
                        <div>
                          <span className="text-gray-400">Class</span>
                          <div>{equasis.data.class_society}</div>
                        </div>
                      )}
                      {equasis.data.year_built && (
                        <div>
                          <span className="text-gray-400">Built</span>
                          <div>{equasis.data.year_built}</div>
                        </div>
                      )}
                      {equasis.data.gross_tonnage && (
                        <div>
                          <span className="text-gray-400">GT</span>
                          <div>{Number(equasis.data.gross_tonnage).toLocaleString()}</div>
                        </div>
                      )}
                      {equasis.data.deadweight && (
                        <div>
                          <span className="text-gray-400">DWT</span>
                          <div>{Number(equasis.data.deadweight).toLocaleString()}</div>
                        </div>
                      )}
                    </div>
                    {equasis.data.inspections && equasis.data.inspections.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Inspections ({equasis.data.inspections.length})</div>
                        <div className="space-y-1 max-h-24 overflow-y-auto">
                          {equasis.data.inspections.slice(0, 5).map((ins: any, i: number) => (
                            <div key={i} className="text-[10px] bg-navy-700/50 rounded px-2 py-1 flex justify-between">
                              <span className="text-gray-300">{ins.authority || ins.type || 'Inspection'}</span>
                              <span className={ins.deficiencies > 0 ? 'text-amber-400' : 'text-green-400'}>
                                {ins.deficiencies ?? 0} deficiencies
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {equasis.data.flag_history && equasis.data.flag_history.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Flag history</div>
                        <div className="text-[10px] text-gray-500">
                          {equasis.data.flag_history.map((f: any, i: number) => (
                            <span key={i}>{f.flag}{i < equasis.data.flag_history.length - 1 ? ' → ' : ''}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="flex items-center justify-between mt-1">
                      {equasis.source && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          equasis.source === 'equasis'
                            ? 'bg-violet-900/40 text-violet-400'
                            : 'bg-navy-600 text-gray-400'
                        }`}>
                          {equasis.source === 'equasis' ? 'Equasis Registry' : 'AIS-Derived'}
                        </span>
                      )}
                      {equasis.cached_at && (
                        <span className="text-[10px] text-gray-500">
                          {new Date(equasis.cached_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </>
                )}
                {equasis && !equasis.data && !equasisLoading && (
                  <p className="text-xs text-gray-500">No registry data available for this vessel.</p>
                )}
                {!equasis && !equasisLoading && (
                  <p className="text-xs text-gray-500">Click to look up vessel registry.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Bottom spacing */}
        <div className="h-4" />
      </div>
    </div>
  )
}
