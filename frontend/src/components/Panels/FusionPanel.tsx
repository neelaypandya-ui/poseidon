import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { computeFusion, getFusionHistory, type FusionResult } from '../../hooks/useFusion'

function ConfidenceBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-navy-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${(value * 100).toFixed(0)}%` }} />
      </div>
      <span className="text-xs text-gray-300 w-10 text-right">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

export default function FusionPanel() {
  const selectedMmsi = useVesselStore((s) => s.selectedMmsi)
  const [result, setResult] = useState<FusionResult | null>(null)
  const [history, setHistory] = useState<FusionResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  const handleCompute = async () => {
    if (!selectedMmsi) return
    setError(null)
    setLoading(true)
    try {
      const res = await computeFusion(selectedMmsi)
      setResult(res)
      const hist = await getFusionHistory(selectedMmsi, 10)
      setHistory(hist)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Fusion computation failed')
    } finally {
      setLoading(false)
    }
  }

  if (!selectedMmsi) return null

  const posteriorColor = result
    ? result.posterior_score >= 0.8 ? 'text-green-400'
    : result.posterior_score >= 0.5 ? 'text-cyan-400'
    : result.posterior_score >= 0.3 ? 'text-yellow-400'
    : 'text-red-400'
    : ''

  return (
    <div className="absolute bottom-4 right-4 w-80 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg overflow-hidden z-20">
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="w-full px-3 py-2 bg-cyan-900/20 border-b border-navy-600 flex justify-between items-center hover:bg-cyan-900/30 transition-colors"
      >
        <div className="text-left">
          <h3 className="text-cyan-400 font-semibold text-sm">Signal Fusion</h3>
          <p className="text-[10px] text-gray-500">Combines AIS, SAR, VIIRS &amp; acoustic signals into a single confidence score</p>
        </div>
        <span className="text-cyan-400 text-xs ml-2 shrink-0">{isOpen ? '▼' : '▶'}</span>
      </button>

      {isOpen && (
        <>
          <div className="px-3 py-1.5 flex justify-end">
            <button
              onClick={handleCompute}
              disabled={loading}
              className="text-xs bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white px-2 py-0.5 rounded transition-colors"
            >
              {loading ? 'Computing...' : 'Compute'}
            </button>
          </div>

          {error && <p className="px-3 py-1 text-xs text-red-400">{error}</p>}

          {result && (
            <div className="p-3 pt-0 space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">MMSI {result.mmsi}</span>
                <span className={`text-sm font-bold ${posteriorColor}`}>
                  {(result.posterior_score * 100).toFixed(0)}% {result.classification}
                </span>
              </div>

              <div className="space-y-1.5">
                <ConfidenceBar label="AIS" value={result.ais_confidence} color="bg-cyan-500" />
                <ConfidenceBar label="SAR" value={result.sar_confidence} color="bg-amber-500" />
                <ConfidenceBar label="VIIRS" value={result.viirs_confidence} color="bg-orange-500" />
                <ConfidenceBar label="Acoustic" value={result.acoustic_confidence} color="bg-purple-500" />
              </div>

              <div className="text-xs text-gray-500 mt-1">
                {new Date(result.timestamp).toLocaleString()}
              </div>
            </div>
          )}

          {history.length > 1 && (
            <div className="px-3 pb-2">
              <div className="text-xs text-gray-500 mb-1">History ({history.length})</div>
              <div className="flex gap-0.5 h-8 items-end">
                {history.slice().reverse().map((h, i) => (
                  <div
                    key={h.id || i}
                    className="flex-1 bg-cyan-600/60 rounded-t"
                    style={{ height: `${h.posterior_score * 100}%` }}
                    title={`${(h.posterior_score * 100).toFixed(0)}% - ${new Date(h.timestamp).toLocaleDateString()}`}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
