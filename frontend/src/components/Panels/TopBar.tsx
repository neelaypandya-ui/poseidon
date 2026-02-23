import { useVesselStore } from '../../stores/vesselStore'

export default function TopBar() {
  const vesselCount = useVesselStore((s) => s.vesselCount)
  const searchQuery = useVesselStore((s) => s.searchQuery)
  const setSearchQuery = useVesselStore((s) => s.setSearchQuery)
  const filteredCount = useVesselStore((s) => s.filteredCount)

  return (
    <div className="absolute top-0 left-0 right-0 h-12 bg-navy-800/90 backdrop-blur border-b border-navy-600 flex items-center px-4 z-30 gap-4">
      <h1 className="text-cyan-400 font-bold text-lg tracking-wide mr-4">POSEIDON</h1>

      <div className="relative flex-1 max-w-md">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search MMSI or vessel name..."
          className="w-full bg-navy-700 border border-navy-600 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
          >
            &times;
          </button>
        )}
      </div>

      <div className="text-sm text-gray-400">
        {searchQuery ? (
          <>
            <span className="text-yellow-400 font-mono">{filteredCount.toLocaleString()}</span>
            <span className="text-gray-500"> / {vesselCount.toLocaleString()}</span> vessels
          </>
        ) : (
          <>
            <span className="text-cyan-400 font-mono">{vesselCount.toLocaleString()}</span> vessels
          </>
        )}
      </div>
    </div>
  )
}
