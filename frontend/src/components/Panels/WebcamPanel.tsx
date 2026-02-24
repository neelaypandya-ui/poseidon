import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Webcam {
  id: number
  name: string
  stream_url: string
  thumbnail_url: string | null
  lon: number | null
  lat: number | null
  country_code: string | null
  port_locode: string | null
  status: string
}

export default function WebcamPanel({ isOpen }: { isOpen: boolean }) {
  const [webcams, setWebcams] = useState<Webcam[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedCam, setSelectedCam] = useState<Webcam | null>(null)

  useEffect(() => {
    if (isOpen && webcams.length === 0) {
      setLoading(true)
      axios
        .get(`${API_URL}/api/v1/webcams`)
        .then(({ data }) => setWebcams(data.webcams || []))
        .catch(console.error)
        .finally(() => setLoading(false))
    }
  }, [isOpen, webcams.length])

  if (!isOpen) return null

  return (
        <div className="w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-teal-900/20 border-b border-navy-600">
            <h3 className="text-teal-400 font-semibold text-sm">
              Port Webcams
              {webcams.length > 0 && (
                <span className="ml-2 text-xs text-gray-400 font-normal">({webcams.length})</span>
              )}
            </h3>
          </div>

          {loading && (
            <div className="px-3 py-4 text-xs text-gray-400 text-center">Loading webcams...</div>
          )}

          {selectedCam && (
            <div className="px-3 py-2 border-b border-navy-700 bg-navy-700/50">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-xs font-medium text-white">{selectedCam.name}</div>
                  <div className="text-xs text-gray-400">
                    {selectedCam.country_code} {selectedCam.port_locode && `| ${selectedCam.port_locode}`}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedCam(null)}
                  className="text-gray-400 hover:text-white text-xs"
                >
                  x
                </button>
              </div>
              <a
                href={selectedCam.stream_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-xs text-cyan-400 hover:text-cyan-300 underline"
              >
                Open Stream
              </a>
            </div>
          )}

          <div className="max-h-64 overflow-y-auto">
            {!loading && webcams.length === 0 && (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">No webcams available.</div>
            )}
            {webcams.map((cam) => (
              <div
                key={cam.id}
                className="px-3 py-2 border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer"
                onClick={() => setSelectedCam(cam)}
              >
                <div className="flex justify-between items-center">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-white truncate">{cam.name}</div>
                    <div className="text-xs text-gray-400">
                      {cam.country_code || '??'}
                      {cam.lon && cam.lat && (
                        <span className="ml-1 text-gray-500">
                          ({cam.lat.toFixed(1)}, {cam.lon.toFixed(1)})
                        </span>
                      )}
                    </div>
                  </div>
                  <span className={`text-xs ${cam.status === 'active' ? 'text-green-400' : 'text-gray-500'}`}>
                    {cam.status === 'active' ? '\u25CF' : '\u25CB'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
  )
}
