import { useEffect, useMemo, useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchVesselDetail } from '../../hooks/useVessels'
import { predictRoute } from '../../hooks/useRoutes'
import { getFlagFromMmsi } from '../../utils/flags'
import { computeRiskScore, getRiskScore, getReportUrl, type RiskScore } from '../../hooks/useRisk'
import { computeFusion, getFusionHistory, type FusionResult } from '../../hooks/useFusion'

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

  useEffect(() => {
    if (!selectedMmsi) {
      setDetail(null)
      setRisk(null)
      setFusion(null)
      setFusionHistory([])
      setRiskOpen(false)
      setFusionOpen(false)
      return
    }
    setLoading(true)
    fetchVesselDetail(selectedMmsi)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
    getRiskScore(selectedMmsi).then(setRisk)
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

        {/* Bottom spacing */}
        <div className="h-4" />
      </div>
    </div>
  )
}
