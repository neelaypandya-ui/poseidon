import { useState, useEffect } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchAOIs, createAOI, deleteAOI, fetchAOIEvents, type AOI, type AOIEvent } from '../../hooks/useAOI'

export default function AOIPanel({ isOpen }: { isOpen: boolean }) {
  const [aois, setAois] = useState<AOI[]>([])
  const [selectedAoi, setSelectedAoi] = useState<number | null>(null)
  const [events, setEvents] = useState<AOIEvent[]>([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const drawingAoi = useVesselStore((s) => s.drawingAoi)
  const setDrawingAoi = useVesselStore((s) => s.setDrawingAoi)
  const aoiPolygonPoints = useVesselStore((s) => s.aoiPolygonPoints)
  const setAoiPolygonPoints = useVesselStore((s) => s.setAoiPolygonPoints)
  const setAoiGeoJsons = useVesselStore((s) => s.setAoiGeoJsons)

  const refresh = () => {
    fetchAOIs().then((a) => {
      setAois(a)
      setAoiGeoJsons(a.map((x) => x.geojson).filter(Boolean))
    })
  }

  useEffect(() => {
    if (isOpen) refresh()
  }, [isOpen])

  useEffect(() => {
    if (selectedAoi) {
      fetchAOIEvents(selectedAoi).then(setEvents)
    }
  }, [selectedAoi])

  const handleStartDraw = () => {
    setDrawingAoi(true)
    setAoiPolygonPoints([])
    setCreating(true)
  }

  const handleFinishDraw = async () => {
    if (aoiPolygonPoints.length < 3 || !newName.trim()) return
    await createAOI(newName.trim(), aoiPolygonPoints as [number, number][])
    setDrawingAoi(false)
    setAoiPolygonPoints([])
    setCreating(false)
    setNewName('')
    refresh()
  }

  const handleCancelDraw = () => {
    setDrawingAoi(false)
    setAoiPolygonPoints([])
    setCreating(false)
    setNewName('')
  }

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    await deleteAOI(id)
    if (selectedAoi === id) setSelectedAoi(null)
    refresh()
  }

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-teal-900/50 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-teal-900/30 border-b border-teal-900/50 flex items-center justify-between">
            <h3 className="text-teal-400 font-semibold text-sm">Areas of Interest</h3>
            {!creating && (
              <button
                onClick={handleStartDraw}
                className="text-teal-400 text-xs bg-teal-900/40 px-2 py-0.5 rounded hover:bg-teal-900/60"
              >
                + Draw Zone
              </button>
            )}
          </div>

          {creating && (
            <div className="px-3 py-2 border-b border-navy-700 bg-teal-900/10">
              <div className="text-xs text-teal-300 mb-1">
                {drawingAoi
                  ? `Click map to add points (${aoiPolygonPoints.length} placed). Double-click to finish.`
                  : 'Enter a name and click Draw Zone.'}
              </div>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Zone name..."
                className="w-full bg-navy-700 text-sm text-white px-2 py-1 rounded border border-navy-600 mb-1"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleFinishDraw}
                  disabled={aoiPolygonPoints.length < 3 || !newName.trim()}
                  className="flex-1 text-xs bg-teal-600 text-white py-1 rounded disabled:opacity-40"
                >
                  Save ({aoiPolygonPoints.length} pts)
                </button>
                <button
                  onClick={handleCancelDraw}
                  className="flex-1 text-xs bg-navy-600 text-gray-300 py-1 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="overflow-y-auto max-h-64">
            {aois.length === 0 && !creating ? (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">
                No areas defined. Click "+ Draw Zone" to create one.
              </div>
            ) : (
              aois.map((aoi) => (
                <div key={aoi.id} className="border-b border-navy-700">
                  <div
                    onClick={() => setSelectedAoi(selectedAoi === aoi.id ? null : aoi.id)}
                    className="px-3 py-2 hover:bg-navy-700/50 cursor-pointer transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-sm font-medium text-teal-300">{aoi.name}</div>
                        {aoi.description && (
                          <div className="text-[10px] text-gray-500">{aoi.description}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-teal-500">
                          {aoi.vessels_inside} inside
                        </span>
                        <button
                          onClick={(e) => handleDelete(aoi.id, e)}
                          className="text-gray-600 hover:text-red-400 text-xs"
                        >
                          x
                        </button>
                      </div>
                    </div>
                  </div>

                  {selectedAoi === aoi.id && (
                    <div className="px-3 pb-2 bg-navy-900/50">
                      <div className="text-[10px] text-gray-400 mb-1">Recent Events</div>
                      {events.length === 0 ? (
                        <div className="text-[10px] text-gray-600">No events yet</div>
                      ) : (
                        events.slice(0, 8).map((ev) => (
                          <div key={ev.id} className="flex justify-between text-[10px] text-gray-400 py-0.5">
                            <span>
                              <span
                                className={
                                  ev.event_type === 'entry'
                                    ? 'text-green-400'
                                    : ev.event_type === 'exit'
                                      ? 'text-red-400'
                                      : 'text-amber-400'
                                }
                              >
                                {ev.event_type.toUpperCase()}
                              </span>{' '}
                              {ev.vessel_name || `MMSI ${ev.mmsi}`}
                            </span>
                            <span>{new Date(ev.occurred_at).toLocaleTimeString()}</span>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
  )
}
