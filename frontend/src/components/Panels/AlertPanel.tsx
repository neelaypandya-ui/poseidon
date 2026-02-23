import { useVesselStore } from '../../stores/vesselStore'

export default function AlertPanel() {
  const darkAlerts = useVesselStore((s) => s.darkAlerts)

  if (darkAlerts.length === 0) return null

  return (
    <div className="absolute bottom-4 left-4 w-72 max-h-64 bg-navy-800/95 backdrop-blur border border-red-900/50 rounded-lg overflow-hidden z-20">
      <div className="px-3 py-2 bg-red-900/30 border-b border-red-900/50">
        <h3 className="text-red-400 font-semibold text-sm">
          Dark Vessel Alerts ({darkAlerts.length})
        </h3>
      </div>
      <div className="overflow-y-auto max-h-48">
        {darkAlerts.map((alert) => (
          <div
            key={alert.id}
            className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer"
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
                {alert.gap_hours != null ? `${alert.gap_hours.toFixed(1)}h` : '—'}
              </div>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Last: {new Date(alert.last_seen_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
