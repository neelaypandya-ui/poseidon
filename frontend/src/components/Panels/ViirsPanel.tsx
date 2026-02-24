import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchViirs, fetchViirsAnomalies } from '../../hooks/useViirs'

export default function ViirsPanel({ isOpen }: { isOpen: boolean }) {
  const viirsAnomalies = useVesselStore((s) => s.viirsAnomalies)
  const [bboxStr, setBboxStr] = useState('')
  const [days, setDays] = useState(1)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const parseBbox = (): [number, number, number, number] | undefined => {
    if (!bboxStr.trim()) return undefined
    const parts = bboxStr.split(',').map(Number)
    if (parts.length !== 4 || parts.some(isNaN)) return undefined
    return parts as [number, number, number, number]
  }

  const handleFetch = async () => {
    setError(null)
    setFetching(true)
    try {
      const bbox = parseBbox()
      await fetchViirs(bbox, days)
      // Poll anomalies after a short delay
      setTimeout(async () => {
        await fetchViirsAnomalies(bbox)
      }, 3000)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Fetch failed')
    } finally {
      setFetching(false)
    }
  }

  const handleRefreshAnomalies = async () => {
    try {
      await fetchViirsAnomalies(parseBbox())
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Refresh failed')
    }
  }

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-orange-900/20 border-b border-navy-600">
            <h3 className="text-orange-400 font-semibold text-sm">VIIRS Nighttime Lights</h3>
          </div>

          <div className="p-3 space-y-2 border-b border-navy-700">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Bbox (optional)</label>
              <input
                type="text" value={bboxStr} onChange={(e) => setBboxStr(e.target.value)}
                placeholder="-10,35,30,60"
                className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Lookback Days: {days}</label>
              <input type="range" min={1} max={10} value={days}
                onChange={(e) => setDays(Number(e.target.value))} className="w-full" />
            </div>
            <button onClick={handleFetch} disabled={fetching}
              className="w-full bg-orange-600 hover:bg-orange-500 disabled:bg-orange-800 text-white text-sm font-medium py-1.5 rounded transition-colors">
              {fetching ? 'Fetching...' : 'Fetch VIIRS Data'}
            </button>
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>

          {viirsAnomalies.length > 0 && (
            <>
              <div className="px-3 py-1.5 bg-orange-900/10 border-b border-navy-700">
                <span className="text-xs text-orange-300 font-medium">
                  {viirsAnomalies.length} anomalies detected
                </span>
              </div>
              <div className="max-h-48 overflow-y-auto">
                {viirsAnomalies.map((a) => (
                  <div key={a.id} className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-xs font-medium text-white">
                          {a.lat.toFixed(3)}, {a.lon.toFixed(3)}
                        </div>
                        <div className="text-xs text-gray-400">
                          {a.anomaly_type || 'hotspot'}
                          {a.anomaly_ratio != null && ` \u00B7 ${a.anomaly_ratio.toFixed(1)}x baseline`}
                        </div>
                      </div>
                      <div className="text-xs text-orange-400 font-mono">
                        {a.radiance.toFixed(1)} nW
                      </div>
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {a.observation_date}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="px-3 py-2">
            <button onClick={handleRefreshAnomalies}
              className="w-full text-xs text-orange-400 hover:text-orange-300 transition-colors">
              Refresh Anomalies
            </button>
          </div>
        </div>
  )
}
