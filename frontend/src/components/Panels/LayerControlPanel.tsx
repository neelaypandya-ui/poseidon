import { useVesselStore } from '../../stores/vesselStore'

export default function LayerControlPanel() {
  const vesselLayerVisible = useVesselStore((s) => s.vesselLayerVisible)
  const setVesselLayerVisible = useVesselStore((s) => s.setVesselLayerVisible)

  return (
    <div className="absolute top-16 left-4 bg-navy-800/95 backdrop-blur border border-navy-600 rounded-lg p-3 z-20">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Layers
      </h3>
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          checked={vesselLayerVisible}
          onChange={(e) => setVesselLayerVisible(e.target.checked)}
          className="rounded border-navy-600 bg-navy-700 text-cyan-500 focus:ring-cyan-500"
        />
        <span>Vessels</span>
      </label>
    </div>
  )
}
