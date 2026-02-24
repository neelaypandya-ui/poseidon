import { useState, useEffect } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchWatchlist, removeFromWatchlist, type WatchlistItem } from '../../hooks/useWatchlist'
import { fetchVesselTrack } from '../../hooks/useVessels'

export default function WatchlistPanel({ isOpen }: { isOpen: boolean }) {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(false)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)

  const refresh = () => {
    setLoading(true)
    fetchWatchlist().then(setItems).finally(() => setLoading(false))
  }

  useEffect(() => {
    if (isOpen && items.length === 0) refresh()
  }, [isOpen])

  const handleClick = async (mmsi: number) => {
    setSelectedMmsi(mmsi)
    try {
      const track = await fetchVesselTrack(mmsi)
      setSelectedTrack(track || [])
    } catch {
      setSelectedTrack([])
    }
  }

  const handleRemove = async (mmsi: number, e: React.MouseEvent) => {
    e.stopPropagation()
    await removeFromWatchlist(mmsi)
    setItems((prev) => prev.filter((i) => i.mmsi !== mmsi))
  }

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-indigo-900/50 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-indigo-900/30 border-b border-indigo-900/50 flex items-center justify-between">
            <h3 className="text-indigo-400 font-semibold text-sm">Watched Vessels</h3>
            <button onClick={refresh} className="text-indigo-400 text-xs hover:text-indigo-300">
              {loading ? '...' : 'Refresh'}
            </button>
          </div>
          <div className="overflow-y-auto max-h-72">
            {items.length === 0 ? (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">
                No vessels on watchlist. Click a vessel and use "Add to Watchlist" to track it.
              </div>
            ) : (
              items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleClick(item.mmsi)}
                  className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-sm font-medium">
                        {item.vessel_name || `MMSI ${item.mmsi}`}
                      </div>
                      {item.label && (
                        <div className="text-[10px] text-indigo-400">{item.label}</div>
                      )}
                      <div className="text-xs text-gray-500 capitalize">
                        {item.ship_type || 'unknown'}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleRemove(item.mmsi, e)}
                      className="text-gray-600 hover:text-red-400 text-xs px-1"
                      title="Remove from watchlist"
                    >
                      x
                    </button>
                  </div>
                  <div className="mt-1 flex justify-between text-xs text-gray-500">
                    {item.lon != null && item.lat != null ? (
                      <span>
                        {item.lat.toFixed(3)}, {item.lon.toFixed(3)}
                      </span>
                    ) : (
                      <span>No position</span>
                    )}
                    {item.sog != null && <span>{item.sog.toFixed(1)} kn</span>}
                  </div>
                  {item.last_seen && (
                    <div className="text-[10px] text-gray-600">
                      Last seen: {new Date(item.last_seen).toLocaleString()}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
  )
}
