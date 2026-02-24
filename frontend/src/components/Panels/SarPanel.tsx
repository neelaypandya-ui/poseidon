import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { searchSarScenes, processSarScene, fetchSarDetections } from '../../hooks/useSar'

export default function SarPanel({ isOpen }: { isOpen: boolean }) {
  const sarScenes = useVesselStore((s) => s.sarScenes)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [bboxStr, setBboxStr] = useState('')
  const [searching, setSearching] = useState(false)
  const [processingId, setProcessingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    setError(null)
    if (!startDate || !endDate) {
      setError('Select start and end dates')
      return
    }

    let bbox: [number, number, number, number]
    if (bboxStr.trim()) {
      const parts = bboxStr.split(',').map(Number)
      if (parts.length !== 4 || parts.some(isNaN)) {
        setError('Bbox format: min_lon,min_lat,max_lon,max_lat')
        return
      }
      bbox = parts as [number, number, number, number]
    } else {
      // Default: global
      bbox = [-180, -90, 180, 90]
    }

    setSearching(true)
    try {
      await searchSarScenes(bbox, startDate, endDate)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  const handleProcess = async (sceneDbId: number) => {
    setProcessingId(sceneDbId)
    try {
      await processSarScene(sceneDbId)
      // Poll detections after a short delay
      setTimeout(() => fetchSarDetections(), 3000)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Processing failed')
    } finally {
      setProcessingId(null)
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400'
      case 'processing': case 'downloading': return 'text-yellow-400'
      case 'failed': return 'text-red-400'
      default: return 'text-gray-400'
    }
  }

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-amber-900/20 border-b border-navy-600">
            <h3 className="text-amber-400 font-semibold text-sm">
              Sentinel-1 SAR Search
            </h3>
          </div>

          <div className="p-3 space-y-2 border-b border-navy-700">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Bbox (lon1,lat1,lon2,lat2)</label>
              <input
                type="text"
                value={bboxStr}
                onChange={(e) => setBboxStr(e.target.value)}
                placeholder="-10,35,30,60"
                className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">Start</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">End</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
            <button
              onClick={handleSearch}
              disabled={searching}
              className="w-full bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 text-white text-sm font-medium py-1.5 rounded transition-colors"
            >
              {searching ? 'Searching...' : 'Search Scenes'}
            </button>
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>

          {sarScenes.length > 0 && (
            <div className="max-h-64 overflow-y-auto">
              {sarScenes.map((scene) => (
                <div
                  key={scene.id}
                  className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-white truncate">{scene.title}</div>
                      <div className="text-xs text-gray-400">
                        {new Date(scene.acquisition_date).toLocaleDateString()} &middot; {scene.platform}
                      </div>
                    </div>
                    <span className={`text-xs font-mono ml-2 ${statusColor(scene.status)}`}>
                      {scene.status}
                    </span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-xs text-gray-500">
                      {scene.detection_count > 0
                        ? `${scene.detection_count} detections`
                        : 'No detections yet'}
                    </span>
                    {scene.status === 'pending' && (
                      <button
                        onClick={() => handleProcess(scene.id)}
                        disabled={processingId === scene.id}
                        className="text-xs bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white px-2 py-0.5 rounded transition-colors"
                      >
                        {processingId === scene.id ? 'Queued...' : 'Process'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="px-3 py-2">
            <button
              onClick={() => fetchSarDetections()}
              className="w-full text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              Refresh Detections
            </button>
          </div>
        </div>
  )
}
