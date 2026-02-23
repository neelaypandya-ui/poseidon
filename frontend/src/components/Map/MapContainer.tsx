import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Map, { MapRef } from 'react-map-gl/maplibre'
import { MapViewState } from '@deck.gl/core'
import DeckGL from '@deck.gl/react'
import { ScatterplotLayer, PathLayer } from '@deck.gl/layers'
import type { PickingInfo } from '@deck.gl/core'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useVesselStore, type Vessel } from '../../stores/vesselStore'
import { getVesselColor } from '../../utils/colors'
import { fetchVesselTrack } from '../../hooks/useVessels'

const INITIAL_VIEW: MapViewState = {
  longitude: 0,
  latitude: 20,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
}

const CARTO_DARK = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

export default function MapContainer() {
  const vessels = useVesselStore((s) => s.vessels)
  const selectedMmsi = useVesselStore((s) => s.selectedMmsi)
  const setSelectedMmsi = useVesselStore((s) => s.setSelectedMmsi)
  const selectedTrack = useVesselStore((s) => s.selectedTrack)
  const setSelectedTrack = useVesselStore((s) => s.setSelectedTrack)
  const darkAlerts = useVesselStore((s) => s.darkAlerts)
  const vesselLayerVisible = useVesselStore((s) => s.vesselLayerVisible)
  const searchQuery = useVesselStore((s) => s.searchQuery)
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)
  const mapRef = useRef<MapRef>(null)

  const vesselArray = useMemo(() => {
    const all = Array.from(vessels.values())
    if (!searchQuery) return all
    const q = searchQuery.toLowerCase()
    const filtered = all.filter(
      (v) =>
        String(v.mmsi).includes(q) ||
        (v.name && v.name.toLowerCase().includes(q)),
    )
    return filtered
  }, [vessels, searchQuery])

  // Sync filtered count back to store for TopBar display
  const setFilteredCount = useVesselStore((s) => s.setFilteredCount)
  useEffect(() => {
    setFilteredCount(vesselArray.length)
  }, [vesselArray.length, setFilteredCount])

  const handleClick = useCallback(
    async (info: PickingInfo) => {
      if (info.object && 'mmsi' in info.object) {
        const mmsi = (info.object as Vessel).mmsi
        setSelectedMmsi(mmsi)
        try {
          const track = await fetchVesselTrack(mmsi)
          setSelectedTrack(track || [])
        } catch {
          setSelectedTrack([])
        }
      } else {
        setSelectedMmsi(null)
        setSelectedTrack([])
      }
    },
    [setSelectedMmsi, setSelectedTrack],
  )

  const onViewStateChange = useCallback(
    ({ viewState: vs }: any) => setViewState(vs as MapViewState),
    [],
  )

  const getCursor = useCallback(
    ({ isHovering }: { isHovering: boolean }) => (isHovering ? 'pointer' : 'grab'),
    [],
  )

  // Pulsing effect for dark vessel alerts
  const [pulsePhase, setPulsePhase] = useState(0)
  useEffect(() => {
    if (darkAlerts.length === 0) return
    const id = setInterval(() => setPulsePhase((p) => (p + 1) % 60), 50)
    return () => clearInterval(id)
  }, [darkAlerts.length])

  // --- Split layer memos ---

  const vesselLayer = useMemo(() => {
    if (!vesselLayerVisible || vesselArray.length === 0) return null
    return new ScatterplotLayer<Vessel>({
      id: 'vessels',
      data: vesselArray,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => getVesselColor(d.ship_type),
      getRadius: (d) => (d.mmsi === selectedMmsi ? 8 : 5),
      radiusMinPixels: 3,
      radiusMaxPixels: 12,
      pickable: true,
      radiusUnits: 'pixels',
      updateTriggers: {
        getRadius: selectedMmsi,
      },
    })
  }, [vesselArray, selectedMmsi, vesselLayerVisible])

  const trackLayer = useMemo(() => {
    if (selectedTrack.length <= 1) return null
    return new PathLayer({
      id: 'vessel-track',
      data: [
        {
          path: selectedTrack.map((p) => [p.lon, p.lat]),
        },
      ],
      getPath: (d: any) => d.path,
      getColor: [80, 200, 255, 180],
      getWidth: 2,
      widthMinPixels: 2,
      widthMaxPixels: 4,
      jointRounded: true,
      capRounded: true,
    })
  }, [selectedTrack])

  const darkAlertsLayer = useMemo(() => {
    if (darkAlerts.length === 0) return null
    const pulseRadius = 8 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 4
    return new ScatterplotLayer({
      id: 'dark-alerts',
      data: darkAlerts,
      getPosition: (d: any) => [
        d.predicted_lon ?? d.last_known_lon,
        d.predicted_lat ?? d.last_known_lat,
      ],
      getFillColor: [255, 0, 0, 0],
      getLineColor: [255, 60, 60, 200],
      getRadius: pulseRadius,
      radiusMinPixels: pulseRadius,
      radiusMaxPixels: 20,
      stroked: true,
      lineWidthMinPixels: 2,
      radiusUnits: 'pixels',
      pickable: true,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [darkAlerts, pulsePhase])

  const layers = useMemo(
    () => [vesselLayer, trackLayer, darkAlertsLayer].filter(Boolean),
    [vesselLayer, trackLayer, darkAlertsLayer],
  )

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={onViewStateChange}
        controller={true}
        layers={layers}
        onClick={handleClick}
        getCursor={getCursor}
        style={{ position: 'relative', width: '100%', height: '100%' }}
      >
        <Map
          ref={mapRef}
          mapStyle={CARTO_DARK}
          reuseMaps
        />
      </DeckGL>
    </div>
  )
}
