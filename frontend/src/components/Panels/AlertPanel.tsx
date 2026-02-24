import { useState, useEffect } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchVesselTrack } from '../../hooks/useVessels'
import { fetchCorrelations, type CorrelationPair } from '../../hooks/useSpoof'

const ANOMALY_COLORS: Record<string, string> = {
  impossible_speed: 'bg-red-500',
  sart_on_non_sar: 'bg-amber-500',
  position_jump: 'bg-orange-500',
  no_identity: 'bg-yellow-500',
}

export default function AlertPanel() {
  const darkAlerts = useVesselStore((s) => s.darkAlerts)
  const spoofClusters = useVesselStore((s) => s.spoofClusters)
  const correlationCount = useVesselStore((s) => s.correlationCount)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)
  const [isOpen, setIsOpen] = useState(true)
  const [spoofOpen, setSpoofOpen] = useState(true)
  const [corrOpen, setCorrOpen] = useState(false)
  const [correlations, setCorrelations] = useState<CorrelationPair[]>([])
  const [corrLoading, setCorrLoading] = useState(false)

  useEffect(() => {
    if (corrOpen && correlations.length === 0 && !corrLoading) {
      setCorrLoading(true)
      fetchCorrelations().then(setCorrelations).finally(() => setCorrLoading(false))
    }
  }, [corrOpen, correlations.length, corrLoading])

  if (darkAlerts.length === 0 && spoofClusters.length === 0 && correlationCount === 0) return null

  const handleAlertClick = async (mmsi: number) => {
    setSelectedMmsi(mmsi)
    try {
      const track = await fetchVesselTrack(mmsi)
      setSelectedTrack(track || [])
    } catch {
      setSelectedTrack([])
    }
  }

  return (
    <div className="absolute bottom-4 left-4 w-72 bg-navy-800/95 backdrop-blur border border-red-900/50 rounded-lg overflow-hidden z-20">
      {darkAlerts.length > 0 && (
        <>
          <button
            onClick={() => setIsOpen((o) => !o)}
            className="w-full px-3 py-2 bg-red-900/30 border-b border-red-900/50 flex items-center justify-between hover:bg-red-900/40 transition-colors"
          >
            <h3 className="text-red-400 font-semibold text-sm">
              Dark Vessel Alerts ({darkAlerts.length})
            </h3>
            <span className="text-red-400 text-xs">{isOpen ? '▼' : '▶'}</span>
          </button>
          {isOpen && (
            <div className="overflow-y-auto max-h-64">
              {darkAlerts.map((alert) => (
                <div
                  key={alert.id}
                  onClick={() => handleAlertClick(alert.mmsi)}
                  className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-sm font-medium">
                        {alert.vessel_name || `MMSI ${alert.mmsi}`}
                      </div>
                      <div className="text-xs text-gray-400 capitalize">
                        {alert.ship_type || 'unknown'}
                      </div>
                    </div>
                    <div className="text-xs text-red-400 font-mono">
                      {alert.gap_hours != null ? `${alert.gap_hours.toFixed(1)}h gap` : '—'}
                    </div>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-x-2 text-xs text-gray-500">
                    <span>
                      Last: {alert.last_known_lat.toFixed(3)}, {alert.last_known_lon.toFixed(3)}
                    </span>
                    {alert.predicted_lat != null && alert.predicted_lon != null && (
                      <span>
                        Pred: {alert.predicted_lat.toFixed(3)}, {alert.predicted_lon.toFixed(3)}
                      </span>
                    )}
                    {alert.search_radius_nm != null && (
                      <span>Radius: {alert.search_radius_nm.toFixed(1)} nm</span>
                    )}
                    <span>
                      Detected: {new Date(alert.detected_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    Last seen: {new Date(alert.last_seen_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {spoofClusters.length > 0 && (
        <>
          <button
            onClick={() => setSpoofOpen((o) => !o)}
            className="w-full px-3 py-2 bg-fuchsia-900/30 border-b border-fuchsia-900/50 flex items-center justify-between hover:bg-fuchsia-900/40 transition-colors"
          >
            <h3 className="text-fuchsia-400 font-semibold text-sm">
              Spoof Clusters ({spoofClusters.length})
            </h3>
            <span className="text-fuchsia-400 text-xs">{spoofOpen ? '▼' : '▶'}</span>
          </button>
          {spoofOpen && (
            <div className="overflow-y-auto max-h-48">
              {spoofClusters.map((cluster) => (
                <div
                  key={cluster.id}
                  className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="text-sm font-medium text-fuchsia-300">
                      {cluster.signal_count} signals
                    </div>
                    <div className="flex gap-1">
                      {cluster.anomaly_types.map((t) => (
                        <span
                          key={t}
                          className={`text-[9px] px-1.5 py-0.5 rounded-full text-white ${ANOMALY_COLORS[t] || 'bg-gray-500'}`}
                        >
                          {t.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    <div>
                      {cluster.centroid_lat.toFixed(3)}, {cluster.centroid_lon.toFixed(3)}
                      {cluster.radius_nm != null && ` (r: ${cluster.radius_nm.toFixed(1)} nm)`}
                    </div>
                    <div>
                      {new Date(cluster.window_start).toLocaleTimeString()} -{' '}
                      {new Date(cluster.window_end).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {correlationCount > 0 && (
        <>
          <button
            onClick={() => setCorrOpen((o) => !o)}
            className="w-full px-3 py-2 bg-emerald-900/30 border-b border-emerald-900/50 flex items-center justify-between hover:bg-emerald-900/40 transition-colors"
          >
            <h3 className="text-emerald-400 font-semibold text-sm">
              Spoof-Dark Correlations ({correlationCount})
            </h3>
            <span className="text-emerald-400 text-xs">{corrOpen ? '▼' : '▶'}</span>
          </button>
          {corrOpen && (
            <div className="overflow-y-auto max-h-48">
              {corrLoading ? (
                <div className="px-3 py-3 text-xs text-gray-400">Loading correlations...</div>
              ) : correlations.length === 0 ? (
                <div className="px-3 py-3 text-xs text-gray-500">No correlations found</div>
              ) : (
                correlations.map((c, i) => (
                  <div
                    key={i}
                    onClick={() => handleAlertClick(c.dark_vessel.mmsi)}
                    className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-sm font-medium text-emerald-300">
                          {c.dark_vessel.name || `MMSI ${c.dark_vessel.mmsi}`}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          went dark near spoof {c.spoof_signal.mmsi}
                        </div>
                      </div>
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded-full text-white ${ANOMALY_COLORS[c.spoof_signal.anomaly_type] || 'bg-gray-500'}`}
                      >
                        {c.spoof_signal.anomaly_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="mt-1 grid grid-cols-2 gap-x-2 text-xs text-gray-500">
                      <span>
                        {c.correlation.distance_nm != null
                          ? `${c.correlation.distance_nm} nm apart`
                          : '—'}
                      </span>
                      <span>
                        {c.correlation.time_gap_hours != null
                          ? `${c.correlation.time_gap_hours}h gap`
                          : '—'}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
