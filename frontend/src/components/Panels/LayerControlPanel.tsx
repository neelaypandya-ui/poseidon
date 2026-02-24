import { useState } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import { fetchFusionBatch } from '../../hooks/useFusion'

export default function LayerControlPanel() {
  const vesselLayerVisible = useVesselStore((s) => s.vesselLayerVisible)
  const setVesselLayerVisible = useVesselStore((s) => s.setVesselLayerVisible)
  const sarLayerVisible = useVesselStore((s) => s.sarLayerVisible)
  const toggleSarLayer = useVesselStore((s) => s.toggleSarLayer)
  const ghostVesselLayerVisible = useVesselStore((s) => s.ghostVesselLayerVisible)
  const toggleGhostVesselLayer = useVesselStore((s) => s.toggleGhostVesselLayer)
  const viirsLayerVisible = useVesselStore((s) => s.viirsLayerVisible)
  const toggleViirsLayer = useVesselStore((s) => s.toggleViirsLayer)
  const routeLayerVisible = useVesselStore((s) => s.routeLayerVisible)
  const toggleRouteLayer = useVesselStore((s) => s.toggleRouteLayer)
  const darkAlertLayerVisible = useVesselStore((s) => s.darkAlertLayerVisible)
  const toggleDarkAlertLayer = useVesselStore((s) => s.toggleDarkAlertLayer)
  const spoofLayerVisible = useVesselStore((s) => s.spoofLayerVisible)
  const toggleSpoofLayer = useVesselStore((s) => s.toggleSpoofLayer)
  const spoofHeatmapVisible = useVesselStore((s) => s.spoofHeatmapVisible)
  const toggleSpoofHeatmap = useVesselStore((s) => s.toggleSpoofHeatmap)
  const shippingLaneLayerVisible = useVesselStore((s) => s.shippingLaneLayerVisible)
  const toggleShippingLaneLayer = useVesselStore((s) => s.toggleShippingLaneLayer)
  const criticalRiskMmsis = useVesselStore((s) => s.criticalRiskMmsis)
  const lowConfidenceMmsis = useVesselStore((s) => s.lowConfidenceMmsis)
  const setLowConfidenceMmsis = useVesselStore((s) => s.setLowConfidenceMmsis)
  const riskFusionFilter = useVesselStore((s) => s.riskFusionFilter)
  const setRiskFusionFilter = useVesselStore((s) => s.setRiskFusionFilter)

  // New layer state
  const eezLayerVisible = useVesselStore((s) => s.eezLayerVisible)
  const toggleEezLayer = useVesselStore((s) => s.toggleEezLayer)
  const portsLayerVisible = useVesselStore((s) => s.portsLayerVisible)
  const togglePortsLayer = useVesselStore((s) => s.togglePortsLayer)
  const bathymetryLayerVisible = useVesselStore((s) => s.bathymetryLayerVisible)
  const toggleBathymetryLayer = useVesselStore((s) => s.toggleBathymetryLayer)
  const acousticLayerVisible = useVesselStore((s) => s.acousticLayerVisible)
  const toggleAcousticLayer = useVesselStore((s) => s.toggleAcousticLayer)
  const webcamLayerVisible = useVesselStore((s) => s.webcamLayerVisible)
  const toggleWebcamLayer = useVesselStore((s) => s.toggleWebcamLayer)

  const [scanning, setScanning] = useState(false)

  const handleFusionScan = async () => {
    setScanning(true)
    try {
      const results = await fetchFusionBatch(24)
      const lowConf = new Set<number>()
      for (const r of results) {
        if (r.posterior_score < 0.3) lowConf.add(r.mmsi)
      }
      setLowConfidenceMmsis(lowConf)
    } catch (e) {
      console.error('[Poseidon] Fusion scan failed:', e)
    } finally {
      setScanning(false)
    }
  }

  const pillBase =
    'px-2.5 py-1 text-xs font-medium rounded-full transition-colors cursor-pointer'
  const pillActive = 'bg-cyan-600 text-white'
  const pillInactive = 'bg-navy-700 text-gray-400 hover:bg-navy-600'

  return (
    <div className="absolute top-16 left-4 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg p-3 z-20">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Layers
      </h3>
      <div className="space-y-1.5">
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={vesselLayerVisible}
            onChange={(e) => setVesselLayerVisible(e.target.checked)}
            className="rounded border-navy-600 bg-navy-700 text-cyan-500 focus:ring-cyan-500"
          />
          <span>Vessels</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={sarLayerVisible}
            onChange={toggleSarLayer}
            className="rounded border-navy-600 bg-navy-700 text-amber-500 focus:ring-amber-500"
          />
          <span className="text-amber-300">SAR Detections</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={ghostVesselLayerVisible}
            onChange={toggleGhostVesselLayer}
            className="rounded border-navy-600 bg-navy-700 text-red-500 focus:ring-red-500"
          />
          <span className="text-red-300">Ghost Vessels</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={viirsLayerVisible}
            onChange={toggleViirsLayer}
            className="rounded border-navy-600 bg-navy-700 text-orange-500 focus:ring-orange-500"
          />
          <span className="text-orange-300">VIIRS Anomalies</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={routeLayerVisible}
            onChange={toggleRouteLayer}
            className="rounded border-navy-600 bg-navy-700 text-green-500 focus:ring-green-500"
          />
          <span className="text-green-300">Route Prediction</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={darkAlertLayerVisible}
            onChange={toggleDarkAlertLayer}
            className="rounded border-navy-600 bg-navy-700 text-red-500 focus:ring-red-500"
          />
          <span className="text-red-400">Dark Vessel Alerts</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={spoofLayerVisible}
            onChange={toggleSpoofLayer}
            className="rounded border-navy-600 bg-navy-700 text-fuchsia-500 focus:ring-fuchsia-500"
          />
          <span className="text-fuchsia-400">Spoof Clusters</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={spoofHeatmapVisible}
            onChange={toggleSpoofHeatmap}
            className="rounded border-navy-600 bg-navy-700 text-rose-500 focus:ring-rose-500"
          />
          <span className="text-rose-400">Spoof Heatmap</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={shippingLaneLayerVisible}
            onChange={toggleShippingLaneLayer}
            className="rounded border-navy-600 bg-navy-700 text-sky-500 focus:ring-sky-500"
          />
          <span className="text-sky-400">Shipping Lanes</span>
        </label>

        {/* New overlay layers */}
        <div className="border-t border-navy-700 pt-1.5 mt-1.5">
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={eezLayerVisible}
              onChange={toggleEezLayer}
              className="rounded border-navy-600 bg-navy-700 text-blue-500 focus:ring-blue-500"
            />
            <span className="text-blue-400">EEZ Boundaries</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm mt-1.5">
            <input
              type="checkbox"
              checked={portsLayerVisible}
              onChange={togglePortsLayer}
              className="rounded border-navy-600 bg-navy-700 text-teal-500 focus:ring-teal-500"
            />
            <span className="text-teal-400">Ports</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm mt-1.5">
            <input
              type="checkbox"
              checked={bathymetryLayerVisible}
              onChange={toggleBathymetryLayer}
              className="rounded border-navy-600 bg-navy-700 text-indigo-500 focus:ring-indigo-500"
            />
            <span className="text-indigo-400">Bathymetry (GEBCO)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm mt-1.5">
            <input
              type="checkbox"
              checked={acousticLayerVisible}
              onChange={toggleAcousticLayer}
              className="rounded border-navy-600 bg-navy-700 text-purple-500 focus:ring-purple-500"
            />
            <span className="text-purple-400">Acoustic Events</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm mt-1.5">
            <input
              type="checkbox"
              checked={webcamLayerVisible}
              onChange={toggleWebcamLayer}
              className="rounded border-navy-600 bg-navy-700 text-teal-500 focus:ring-teal-500"
            />
            <span className="text-teal-300">Port Webcams</span>
          </label>
        </div>
      </div>

      <div className="border-t border-navy-600 mt-3 pt-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Filter
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <button
            className={`${pillBase} ${riskFusionFilter === 'all' ? pillActive : pillInactive}`}
            onClick={() => setRiskFusionFilter('all')}
          >
            All
          </button>
          <button
            className={`${pillBase} ${riskFusionFilter === 'critical' ? pillActive : pillInactive}`}
            onClick={() => setRiskFusionFilter('critical')}
          >
            Critical Risk
            {criticalRiskMmsis.size > 0 && (
              <span className="ml-1 text-[10px] opacity-75">({criticalRiskMmsis.size})</span>
            )}
          </button>
          {lowConfidenceMmsis.size > 0 ? (
            <button
              className={`${pillBase} ${riskFusionFilter === 'low_confidence' ? pillActive : pillInactive}`}
              onClick={() => setRiskFusionFilter('low_confidence')}
            >
              Low Confidence
              <span className="ml-1 text-[10px] opacity-75">({lowConfidenceMmsis.size})</span>
            </button>
          ) : (
            <button
              className={`${pillBase} ${pillInactive}`}
              onClick={handleFusionScan}
              disabled={scanning}
            >
              {scanning ? 'Scanning...' : 'Scan Fusion'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
