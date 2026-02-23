import MapContainer from './components/Map/MapContainer'
import TopBar from './components/Panels/TopBar'
import VesselDetailPanel from './components/Panels/VesselDetailPanel'
import AlertPanel from './components/Panels/AlertPanel'
import LayerControlPanel from './components/Panels/LayerControlPanel'
import { useVesselWebSocket } from './hooks/useVesselWebSocket'
import { useVessels } from './hooks/useVessels'

export default function App() {
  useVesselWebSocket()
  const { isLoading } = useVessels()

  return (
    <div className="w-full h-full relative bg-navy-900">
      <MapContainer />
      <TopBar />
      <LayerControlPanel />
      <VesselDetailPanel />
      <AlertPanel />

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-navy-900/80 z-50">
          <div className="text-cyan-400 text-lg animate-pulse">
            Loading vessel data...
          </div>
        </div>
      )}
    </div>
  )
}
