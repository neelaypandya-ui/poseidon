import { useEffect, useMemo, useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchVesselDetail } from '../../hooks/useVessels'
import { getFlagFromMmsi } from '../../utils/flags'

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

export default function VesselDetailPanel() {
  const selectedMmsi = useVesselStore((s) => s.selectedMmsi)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)
  const [detail, setDetail] = useState<VesselDetail | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedMmsi) {
      setDetail(null)
      return
    }
    setLoading(true)
    fetchVesselDetail(selectedMmsi)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [selectedMmsi])

  const flagInfo = useMemo(
    () => (selectedMmsi ? getFlagFromMmsi(selectedMmsi) : null),
    [selectedMmsi],
  )

  if (!selectedMmsi) return null

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
          </div>
        )}
      </div>
    </div>
  )
}
