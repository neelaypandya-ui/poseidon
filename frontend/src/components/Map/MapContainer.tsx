import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Map, { MapRef } from 'react-map-gl/maplibre'
import { MapViewState } from '@deck.gl/core'
import DeckGL from '@deck.gl/react'
import { ScatterplotLayer, PathLayer, GeoJsonLayer } from '@deck.gl/layers'
import { DataFilterExtension } from '@deck.gl/extensions'
import type { DataFilterExtensionProps } from '@deck.gl/extensions'
import type { PickingInfo } from '@deck.gl/core'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useVesselStore, type Vessel, type SarDetection, type ViirsAnomaly } from '../../stores/vesselStore'
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
  const darkAlertLayerVisible = useVesselStore((s) => s.darkAlertLayerVisible)
  const vesselLayerVisible = useVesselStore((s) => s.vesselLayerVisible)
  const searchQuery = useVesselStore((s) => s.searchQuery)
  const criticalRiskMmsis = useVesselStore((s) => s.criticalRiskMmsis)
  const lowConfidenceMmsis = useVesselStore((s) => s.lowConfidenceMmsis)
  const riskFusionFilter = useVesselStore((s) => s.riskFusionFilter)
  const sarDetections = useVesselStore((s) => s.sarDetections)
  const sarLayerVisible = useVesselStore((s) => s.sarLayerVisible)
  const ghostVesselLayerVisible = useVesselStore((s) => s.ghostVesselLayerVisible)
  const viirsAnomalies = useVesselStore((s) => s.viirsAnomalies)
  const viirsLayerVisible = useVesselStore((s) => s.viirsLayerVisible)
  const routePrediction = useVesselStore((s) => s.routePrediction)
  const routeLayerVisible = useVesselStore((s) => s.routeLayerVisible)
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)
  const mapRef = useRef<MapRef>(null)

  const vesselArray = useMemo(() => Array.from(vessels.values()), [vessels])

  const searchMatchSet = useMemo(() => {
    if (!searchQuery) return null
    const q = searchQuery.toLowerCase()
    const matches = new Set<number>()
    for (const v of vesselArray) {
      if (String(v.mmsi).includes(q) || (v.name && v.name.toLowerCase().includes(q)))
        matches.add(v.mmsi)
    }
    return matches
  }, [vesselArray, searchQuery])

  // Sync filtered count back to store for TopBar display
  const setFilteredCount = useVesselStore((s) => s.setFilteredCount)
  useEffect(() => {
    setFilteredCount(searchMatchSet ? searchMatchSet.size : vesselArray.length)
  }, [searchMatchSet, vesselArray.length, setFilteredCount])

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

  // Pulsing effect for dark vessel alerts + ghost vessels + VIIRS + critical highlights
  const [pulsePhase, setPulsePhase] = useState(0)
  const hasGhosts = sarDetections.some((d) => !d.matched)
  const hasViirs = viirsAnomalies.length > 0 && viirsLayerVisible
  const hasCritical = criticalRiskMmsis.size > 0
  useEffect(() => {
    if (darkAlerts.length === 0 && !hasGhosts && !hasViirs && !hasCritical) return
    const id = setInterval(() => setPulsePhase((p) => (p + 1) % 60), 50)
    return () => clearInterval(id)
  }, [darkAlerts.length, hasGhosts, hasViirs, hasCritical])

  // --- Split layer memos ---

  const dataFilter = useMemo(() => new DataFilterExtension({ filterSize: 1 }), [])

  const vesselLayer = useMemo(() => {
    if (!vesselLayerVisible || vesselArray.length === 0) return null
    return new ScatterplotLayer<Vessel, DataFilterExtensionProps<Vessel>>({
      id: 'vessels',
      data: vesselArray,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => getVesselColor(d.ship_type),
      getRadius: (d) => (d.mmsi === selectedMmsi ? 8 : 5),
      radiusMinPixels: 3,
      radiusMaxPixels: 12,
      pickable: true,
      radiusUnits: 'pixels',
      extensions: [dataFilter],
      getFilterValue: (d) => {
        if (searchMatchSet && !searchMatchSet.has(d.mmsi)) return 0
        if (riskFusionFilter === 'critical' && !criticalRiskMmsis.has(d.mmsi)) return 0
        if (riskFusionFilter === 'low_confidence' && !lowConfidenceMmsis.has(d.mmsi)) return 0
        return 1
      },
      filterRange: [1, 1],
      updateTriggers: {
        getRadius: selectedMmsi,
        getFilterValue: [searchMatchSet, riskFusionFilter, criticalRiskMmsis, lowConfidenceMmsis],
      },
    })
  }, [vesselArray, selectedMmsi, vesselLayerVisible, searchMatchSet, dataFilter, riskFusionFilter, criticalRiskMmsis, lowConfidenceMmsis])

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
    if (!darkAlertLayerVisible || darkAlerts.length === 0) return null
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
  }, [darkAlerts, darkAlertLayerVisible, pulsePhase])

  const matchedDetections = useMemo(
    () => sarDetections.filter((d) => d.matched),
    [sarDetections],
  )

  const unmatchedDetections = useMemo(
    () => sarDetections.filter((d) => !d.matched),
    [sarDetections],
  )

  const sarDetectionLayer = useMemo(() => {
    if (!sarLayerVisible || matchedDetections.length === 0) return null
    return new ScatterplotLayer<SarDetection>({
      id: 'sar-detections',
      data: matchedDetections,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: [255, 200, 0, 180],
      getRadius: 6,
      radiusMinPixels: 4,
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [matchedDetections, sarLayerVisible])

  const ghostVesselLayer = useMemo(() => {
    if (!ghostVesselLayerVisible || unmatchedDetections.length === 0) return null
    const pulseRadius = 8 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 4
    return new ScatterplotLayer<SarDetection>({
      id: 'ghost-vessels',
      data: unmatchedDetections,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: [255, 0, 60, 200],
      getLineColor: [255, 60, 60, 255],
      getRadius: pulseRadius,
      radiusMinPixels: pulseRadius,
      stroked: true,
      lineWidthMinPixels: 2,
      radiusUnits: 'pixels',
      pickable: true,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [unmatchedDetections, ghostVesselLayerVisible, pulsePhase])

  const viirsLayer = useMemo(() => {
    if (!viirsLayerVisible || viirsAnomalies.length === 0) return null
    const pulseRadius = 6 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 3
    return new ScatterplotLayer<ViirsAnomaly>({
      id: 'viirs-anomalies',
      data: viirsAnomalies,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: [255, 160, 0, 180],
      getLineColor: [255, 200, 50, 255],
      getRadius: pulseRadius,
      radiusMinPixels: pulseRadius,
      stroked: true,
      lineWidthMinPixels: 1,
      radiusUnits: 'pixels',
      pickable: true,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [viirsAnomalies, viirsLayerVisible, pulsePhase])

  const routePredictionLayer = useMemo(() => {
    if (!routeLayerVisible || !routePrediction || routePrediction.route_geom.length < 2) return null
    return new PathLayer({
      id: 'route-prediction',
      data: [{ path: routePrediction.route_geom }],
      getPath: (d: any) => d.path,
      getColor: [0, 255, 136, 200],
      getWidth: 2,
      widthMinPixels: 2,
      widthMaxPixels: 4,
      getDashArray: [6, 4],
      dashJustified: true,
      jointRounded: true,
      capRounded: true,
    })
  }, [routePrediction, routeLayerVisible])

  const confidenceConeLayer = useMemo(() => {
    if (!routeLayerVisible || !routePrediction) return null
    const features = [routePrediction.confidence_90, routePrediction.confidence_70].filter(Boolean)
    if (features.length === 0) return null
    return new GeoJsonLayer({
      id: 'confidence-cones',
      data: { type: 'FeatureCollection', features },
      getFillColor: (f: any) =>
        f.properties?.confidence >= 0.9 ? [0, 255, 136, 30] : [0, 255, 136, 60],
      getLineColor: [0, 255, 136, 100],
      lineWidthMinPixels: 1,
      stroked: true,
      filled: true,
    })
  }, [routePrediction, routeLayerVisible])

  const criticalVessels = useMemo(
    () => vesselArray.filter((v) => criticalRiskMmsis.has(v.mmsi)),
    [vesselArray, criticalRiskMmsis],
  )

  const criticalHighlightLayer = useMemo(() => {
    if (criticalVessels.length === 0) return null
    const pulseRadius = 12 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 4
    return new ScatterplotLayer<Vessel>({
      id: 'critical-highlights',
      data: criticalVessels,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: [255, 0, 0, 0],
      getLineColor: [255, 40, 40, 220],
      getRadius: pulseRadius,
      radiusMinPixels: pulseRadius,
      radiusMaxPixels: 24,
      stroked: true,
      filled: false,
      lineWidthMinPixels: 2,
      radiusUnits: 'pixels',
      pickable: false,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [criticalVessels, pulsePhase])

  const layers = useMemo(
    () => [confidenceConeLayer, vesselLayer, criticalHighlightLayer, trackLayer, routePredictionLayer, darkAlertsLayer, sarDetectionLayer, ghostVesselLayer, viirsLayer].filter(Boolean),
    [confidenceConeLayer, vesselLayer, criticalHighlightLayer, trackLayer, routePredictionLayer, darkAlertsLayer, sarDetectionLayer, ghostVesselLayer, viirsLayer],
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
          attributionControl={false}
        />
      </DeckGL>
    </div>
  )
}
