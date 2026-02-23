import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import {
  searchOpticalScenes,
  downloadOpticalScene,
  createTimelapse,
  getTimelapseStatus,
  getTimelapseDownloadUrl,
} from '../../hooks/useOptical'

export default function OpticalPanel() {
  const opticalScenes = useVesselStore((s) => s.opticalScenes)
  const [isOpen, setIsOpen] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [bboxStr, setBboxStr] = useState('')
  const [maxCloud, setMaxCloud] = useState(30)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)
  const [timelapseJobId, setTimelapseJobId] = useState<number | null>(null)
  const [timelapseStatus, setTimelapseStatus] = useState<string | null>(null)

  const parseBbox = (): [number, number, number, number] | null => {
    if (!bboxStr.trim()) return [-180, -90, 180, 90]
    const parts = bboxStr.split(',').map(Number)
    if (parts.length !== 4 || parts.some(isNaN)) return null
    return parts as [number, number, number, number]
  }

  const handleSearch = async () => {
    setError(null)
    if (!startDate || !endDate) { setError('Select start and end dates'); return }
    const bbox = parseBbox()
    if (!bbox) { setError('Bbox format: min_lon,min_lat,max_lon,max_lat'); return }
    setSearching(true)
    try {
      await searchOpticalScenes(bbox, startDate, endDate, maxCloud)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  const handleDownload = async (id: number) => {
    setDownloadingId(id)
    try {
      await downloadOpticalScene(id)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Download failed')
    } finally {
      setDownloadingId(null)
    }
  }

  const handleTimelapse = async () => {
    setError(null)
    if (!startDate || !endDate) { setError('Select dates first'); return }
    const bbox = parseBbox()
    if (!bbox) { setError('Invalid bbox'); return }
    try {
      const jobId = await createTimelapse(bbox, startDate, endDate)
      setTimelapseJobId(jobId)
      setTimelapseStatus('pending')
      // Poll status
      const poll = setInterval(async () => {
        const status = await getTimelapseStatus(jobId)
        setTimelapseStatus(status.status)
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(poll)
        }
      }, 5000)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Timelapse creation failed')
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': case 'downloaded': return 'text-green-400'
      case 'processing': case 'downloading': return 'text-yellow-400'
      case 'failed': return 'text-red-400'
      default: return 'text-gray-400'
    }
  }

  return (
    <div className="absolute top-28 right-4 z-20">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg px-3 py-2 text-sm font-medium text-green-400 hover:bg-navy-700/95 transition-colors"
      >
        Optical {isOpen ? '\u25B2' : '\u25BC'}
      </button>

      {isOpen && (
        <div className="mt-1 w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-green-900/20 border-b border-navy-600">
            <h3 className="text-green-400 font-semibold text-sm">Sentinel-2 Optical</h3>
          </div>

          <div className="p-3 space-y-2 border-b border-navy-700">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Bbox (lon1,lat1,lon2,lat2)</label>
              <input
                type="text" value={bboxStr} onChange={(e) => setBboxStr(e.target.value)}
                placeholder="-10,35,30,60"
                className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">Start</label>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500" />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">End</label>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Max Cloud Cover: {maxCloud}%</label>
              <input type="range" min={0} max={100} value={maxCloud}
                onChange={(e) => setMaxCloud(Number(e.target.value))}
                className="w-full" />
            </div>
            <button onClick={handleSearch} disabled={searching}
              className="w-full bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white text-sm font-medium py-1.5 rounded transition-colors">
              {searching ? 'Searching...' : 'Search Scenes'}
            </button>
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>

          {opticalScenes.length > 0 && (
            <div className="max-h-48 overflow-y-auto">
              {opticalScenes.map((scene) => (
                <div key={scene.id} className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-white truncate">{scene.title}</div>
                      <div className="text-xs text-gray-400">
                        {new Date(scene.acquisition_date).toLocaleDateString()}
                        {scene.cloud_cover != null && ` \u00B7 ${scene.cloud_cover.toFixed(0)}% cloud`}
                      </div>
                    </div>
                    <span className={`text-xs font-mono ml-2 ${statusColor(scene.status)}`}>
                      {scene.status}
                    </span>
                  </div>
                  {scene.status === 'pending' && (
                    <button onClick={() => handleDownload(scene.id)}
                      disabled={downloadingId === scene.id}
                      className="mt-1 text-xs bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white px-2 py-0.5 rounded transition-colors">
                      {downloadingId === scene.id ? 'Queued...' : 'Download TCI'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="px-3 py-2 border-t border-navy-700 space-y-2">
            <button onClick={handleTimelapse}
              className="w-full text-xs bg-purple-600 hover:bg-purple-500 text-white py-1.5 rounded transition-colors">
              Generate Timelapse
            </button>
            {timelapseJobId && (
              <div className="text-xs text-gray-400">
                Job #{timelapseJobId}: <span className={statusColor(timelapseStatus || 'pending')}>{timelapseStatus}</span>
                {timelapseStatus === 'completed' && (
                  <a href={getTimelapseDownloadUrl(timelapseJobId)} target="_blank" rel="noreferrer"
                    className="ml-2 text-cyan-400 hover:text-cyan-300 underline">Download MP4</a>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
