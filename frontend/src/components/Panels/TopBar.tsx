import { useState, useRef, useEffect } from 'react'
import { useVesselStore } from '../../stores/vesselStore'
import SarPanel from './SarPanel'
import OpticalPanel from './OpticalPanel'
import ViirsPanel from './ViirsPanel'
import ReplayPanel from './ReplayPanel'
import ScheduledReportsPanel from './ScheduledReportsPanel'
import AOIPanel from './AOIPanel'
import WebcamPanel from './WebcamPanel'
import WatchlistPanel from './WatchlistPanel'

type DropdownId = 'sar' | 'optical' | 'viirs' | 'replay' | 'reports' | 'aoi' | 'webcams' | 'watchlist'

const DROPDOWN_BUTTONS: { id: DropdownId; label: string; color: string }[] = [
  { id: 'watchlist', label: 'Watchlist', color: 'text-indigo-400 hover:bg-indigo-900/30' },
  { id: 'sar', label: 'SAR', color: 'text-amber-400 hover:bg-amber-900/30' },
  { id: 'optical', label: 'Optical', color: 'text-green-400 hover:bg-green-900/30' },
  { id: 'viirs', label: 'VIIRS', color: 'text-orange-400 hover:bg-orange-900/30' },
  { id: 'replay', label: 'Replay', color: 'text-purple-400 hover:bg-purple-900/30' },
  { id: 'reports', label: 'Reports', color: 'text-indigo-400 hover:bg-indigo-900/30' },
  { id: 'aoi', label: 'AOI', color: 'text-teal-400 hover:bg-teal-900/30' },
  { id: 'webcams', label: 'Webcams', color: 'text-teal-400 hover:bg-teal-900/30' },
]

export default function TopBar() {
  const vesselCount = useVesselStore((s) => s.vesselCount)
  const searchQuery = useVesselStore((s) => s.searchQuery)
  const setSearchQuery = useVesselStore((s) => s.setSearchQuery)
  const filteredCount = useVesselStore((s) => s.filteredCount)

  const [activeDropdown, setActiveDropdown] = useState<DropdownId | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setActiveDropdown(null)
      }
    }
    if (activeDropdown) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [activeDropdown])

  const toggleDropdown = (id: DropdownId) => {
    setActiveDropdown((prev) => (prev === id ? null : id))
  }

  return (
    <div className="absolute top-0 left-0 right-0 z-30" ref={dropdownRef}>
      <div className="h-12 bg-navy-800/90 backdrop-blur border-b border-navy-600 flex items-center px-4 gap-4">
        <h1 className="text-cyan-400 font-bold text-lg tracking-wide mr-4 shrink-0">POSEIDON</h1>

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

        <div className="text-sm text-gray-400 shrink-0">
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

        <div className="h-6 w-px bg-navy-600 shrink-0" />

        <div className="flex items-center gap-1 shrink-0">
          {DROPDOWN_BUTTONS.map((btn) => (
            <button
              key={btn.id}
              onClick={() => toggleDropdown(btn.id)}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${btn.color} ${
                activeDropdown === btn.id ? 'bg-navy-600' : 'hover:bg-navy-700'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* Dropdown panel container */}
      {activeDropdown && (
        <div className="absolute right-4 top-full mt-1">
          <SarPanel isOpen={activeDropdown === 'sar'} />
          <OpticalPanel isOpen={activeDropdown === 'optical'} />
          <ViirsPanel isOpen={activeDropdown === 'viirs'} />
          <ReplayPanel isOpen={activeDropdown === 'replay'} />
          <ScheduledReportsPanel isOpen={activeDropdown === 'reports'} />
          <AOIPanel isOpen={activeDropdown === 'aoi'} />
          <WebcamPanel isOpen={activeDropdown === 'webcams'} />
          <WatchlistPanel isOpen={activeDropdown === 'watchlist'} />
        </div>
      )}
    </div>
  )
}
