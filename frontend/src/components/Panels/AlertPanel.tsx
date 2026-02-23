import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchVesselTrack } from '../../hooks/useVessels'

export default function AlertPanel() {
  const darkAlerts = useVesselStore((s) => s.darkAlerts)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)
  const [isOpen, setIsOpen] = useState(true)

  if (darkAlerts.length === 0) return null

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
    </div>
  )
}
