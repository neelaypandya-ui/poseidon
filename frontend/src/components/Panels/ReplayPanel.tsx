import { useState, useEffect, useRef, useCallback } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { createReplayJob, getReplayData, type ReplayData } from '../../hooks/useReplay'
import { exportCanvasVideo, downloadBlob, type ResolutionPreset, getResolution } from '../../utils/videoExport'

export default function ReplayPanel({ isOpen }: { isOpen: boolean }) {
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [mmsiStr, setMmsiStr] = useState('')
  const [speed, setSpeed] = useState(10)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [replayData, setReplayData] = useState<ReplayData | null>(null)

  // Video export state
  const [exporting, setExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState(0)
  const [exportResolution, setExportResolution] = useState<ResolutionPreset>('1080p')

  const replayPlaying = useVesselStore((s) => s.replayPlaying)
  const setReplayPlaying = useVesselStore((s) => s.setReplayPlaying)
  const replayFrameIndex = useVesselStore((s) => s.replayFrameIndex)
  const setReplayFrameIndex = useVesselStore((s) => s.setReplayFrameIndex)
  const batchUpdateVessels = useVesselStore((s) => s.batchUpdateVessels)

  const intervalRef = useRef<number | null>(null)
  const frameRef = useRef(replayFrameIndex)
  frameRef.current = replayFrameIndex

  const handleCreate = async () => {
    setError(null)
    if (!startTime || !endTime) { setError('Set start and end times'); return }
    setLoading(true)
    try {
      const mmsi = mmsiStr ? Number(mmsiStr) : undefined
      const jobId = await createReplayJob({
        mmsi,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        speed,
      })
      const data = await getReplayData(jobId)
      setReplayData(data)
      setReplayFrameIndex(0)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Replay creation failed')
    } finally {
      setLoading(false)
    }
  }

  const applyFrame = useCallback((index: number) => {
    if (!replayData || index >= replayData.frames.length) return
    const frame = replayData.frames[index]
    const vessels = frame.vessels.map((v) => ({
      mmsi: v.mmsi,
      name: null,
      ship_type: 'unknown',
      destination: null,
      lon: v.lon,
      lat: v.lat,
      sog: v.sog,
      cog: v.cog,
      heading: null,
      nav_status: null,
      timestamp: frame.timestamp,
    }))
    batchUpdateVessels(vessels)
  }, [replayData, batchUpdateVessels])

  useEffect(() => {
    if (replayPlaying && replayData) {
      intervalRef.current = window.setInterval(() => {
        const next = frameRef.current + 1
        if (next >= replayData.frames.length) {
          setReplayPlaying(false)
          return
        }
        applyFrame(next)
        setReplayFrameIndex(next)
      }, 1000 / speed)
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [replayPlaying, replayData, speed, applyFrame, setReplayFrameIndex, setReplayPlaying])

  const handleSeek = (index: number) => {
    setReplayFrameIndex(index)
    applyFrame(index)
  }

  const handleExportVideo = async () => {
    const canvas = document.querySelector('canvas') as HTMLCanvasElement | null
    if (!canvas) {
      setError('Canvas not found for video export')
      return
    }

    setExporting(true)
    setExportProgress(0)

    try {
      const res = getResolution(exportResolution)
      const duration = replayData ? replayData.frames.length / speed : 30
      const blob = await exportCanvasVideo(
        canvas,
        {
          width: res.width,
          height: res.height,
          fps: 30,
          duration: Math.min(duration, 300), // Cap at 5 minutes
          filename: `poseidon_replay_${exportResolution}.webm`,
        },
        setExportProgress,
      )
      downloadBlob(blob, `poseidon_replay_${exportResolution}.webm`)
    } catch (e: any) {
      setError(`Export failed: ${e.message}`)
    } finally {
      setExporting(false)
      setExportProgress(0)
    }
  }

  const currentTimestamp = replayData && replayFrameIndex < replayData.frames.length
    ? replayData.frames[replayFrameIndex].timestamp
    : null

  if (!isOpen) return null

  return (
        <div className="w-96 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-purple-900/20 border-b border-navy-600">
            <h3 className="text-purple-400 font-semibold text-sm">Historical Replay</h3>
          </div>

          <div className="p-3 space-y-2">
            <div>
              <label className="block text-xs text-gray-400 mb-1">MMSI (optional)</label>
              <input type="text" value={mmsiStr} onChange={(e) => setMmsiStr(e.target.value)}
                placeholder="All vessels"
                className="w-full bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Start</label>
                <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)}
                  className="w-full min-w-0 bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">End</label>
                <input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)}
                  className="w-full min-w-0 bg-navy-700 border border-navy-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-cyan-500" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Speed: {speed}x</label>
              <input type="range" min={1} max={100} value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))} className="w-full" />
            </div>
            <button onClick={handleCreate} disabled={loading}
              className="w-full bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white text-sm font-medium py-1.5 rounded transition-colors">
              {loading ? 'Loading...' : 'Load Replay'}
            </button>
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>

          {replayData && (
            <div className="px-3 pb-3 space-y-2 border-t border-navy-700 pt-2">
              <div className="flex justify-between items-center">
                <div className="flex gap-2">
                  <button
                    onClick={() => setReplayPlaying(!replayPlaying)}
                    className="text-sm bg-purple-600 hover:bg-purple-500 text-white px-3 py-1 rounded transition-colors"
                  >
                    {replayPlaying ? '\u23F8 Pause' : '\u25B6 Play'}
                  </button>
                  <button
                    onClick={() => handleSeek(0)}
                    className="text-sm bg-navy-600 hover:bg-navy-500 text-white px-2 py-1 rounded transition-colors"
                  >
                    {'\u23EE'}
                  </button>
                </div>
                <span className="text-xs text-gray-400">
                  {replayFrameIndex + 1} / {replayData.total_frames}
                </span>
              </div>

              <input
                type="range"
                min={0}
                max={replayData.total_frames - 1}
                value={replayFrameIndex}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="w-full"
              />

              {currentTimestamp && (
                <div className="text-xs text-center text-cyan-400 font-mono">
                  {new Date(currentTimestamp).toLocaleString()}
                </div>
              )}

              {/* Video Export Section */}
              <div className="border-t border-navy-700 pt-2 space-y-1.5">
                <div className="flex items-center gap-2">
                  <select
                    value={exportResolution}
                    onChange={(e) => setExportResolution(e.target.value as ResolutionPreset)}
                    className="bg-navy-700 border border-navy-600 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="1080p">1080p</option>
                    <option value="1440p">1440p</option>
                    <option value="4K">4K</option>
                  </select>
                  <button
                    onClick={handleExportVideo}
                    disabled={exporting}
                    className="flex-1 text-xs bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white py-1.5 rounded transition-colors"
                  >
                    {exporting ? `Exporting... ${exportProgress.toFixed(0)}%` : 'Export Video'}
                  </button>
                </div>
                {exporting && (
                  <div className="w-full bg-navy-700 rounded-full h-1.5">
                    <div
                      className="bg-cyan-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${exportProgress}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
  )
}
