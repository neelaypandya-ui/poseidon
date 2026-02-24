import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Map, { MapRef, Source, Layer as MapLayer } from 'react-map-gl/maplibre'
import { MapViewState } from '@deck.gl/core'
import DeckGL from '@deck.gl/react'
import { ScatterplotLayer, PathLayer, GeoJsonLayer, TextLayer, PolygonLayer, ArcLayer } from '@deck.gl/layers'
import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import { DataFilterExtension } from '@deck.gl/extensions'
import type { DataFilterExtensionProps } from '@deck.gl/extensions'
import type { PickingInfo } from '@deck.gl/core'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useVesselStore, type Vessel, type SarDetection, type ViirsAnomaly, type SpoofCluster, type AcousticEvent, type ForensicPing } from '../../stores/vesselStore'
import { getVesselColor } from '../../utils/colors'
import { fetchVesselTrack } from '../../hooks/useVessels'
import { fetchSpoofHeatmap, type SpoofHeatmapPoint } from '../../hooks/useSpoof'

const INITIAL_VIEW: MapViewState = {
  longitude: 0,
  latitude: 20,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
}

const CARTO_DARK = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// GEBCO bathymetry WMS
const GEBCO_WMS_URL = 'https://wms.gebco.net/mapserv?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=GEBCO_LATEST_2&STYLES=&SRS=EPSG:3857&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=true'

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
  const spoofClusters = useVesselStore((s) => s.spoofClusters)
  const spoofLayerVisible = useVesselStore((s) => s.spoofLayerVisible)
  const spoofHeatmapVisible = useVesselStore((s) => s.spoofHeatmapVisible)
  const spoofHeatmapData = useVesselStore((s) => s.spoofHeatmapData)
  const setSpoofHeatmapData = useVesselStore((s) => s.setSpoofHeatmapData)
  const shippingLaneLayerVisible = useVesselStore((s) => s.shippingLaneLayerVisible)
  const drawingAoi = useVesselStore((s) => s.drawingAoi)
  const aoiPolygonPoints = useVesselStore((s) => s.aoiPolygonPoints)
  const setAoiPolygonPoints = useVesselStore((s) => s.setAoiPolygonPoints)
  const aoiGeoJsons = useVesselStore((s) => s.aoiGeoJsons)

  // New layer state
  const eezLayerVisible = useVesselStore((s) => s.eezLayerVisible)
  const eezData = useVesselStore((s) => s.eezData)
  const setEezData = useVesselStore((s) => s.setEezData)
  const portsLayerVisible = useVesselStore((s) => s.portsLayerVisible)
  const portsData = useVesselStore((s) => s.portsData)
  const setPortsData = useVesselStore((s) => s.setPortsData)
  const bathymetryLayerVisible = useVesselStore((s) => s.bathymetryLayerVisible)
  const acousticEvents = useVesselStore((s) => s.acousticEvents)
  const acousticLayerVisible = useVesselStore((s) => s.acousticLayerVisible)
  const forensicPings = useVesselStore((s) => s.forensicPings)
  const webcamLayerVisible = useVesselStore((s) => s.webcamLayerVisible)

  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)
  const [maritimeData, setMaritimeData] = useState<any>(null)
  const [webcamData, setWebcamData] = useState<any[]>([])
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

  // Load maritime lane data when layer toggled on
  useEffect(() => {
    if (shippingLaneLayerVisible && !maritimeData) {
      fetch('/data/maritime_lanes.geojson')
        .then((r) => r.json())
        .then(setMaritimeData)
        .catch((e) => console.error('[Poseidon] Failed to load maritime lanes:', e))
    }
  }, [shippingLaneLayerVisible, maritimeData])

  // Load EEZ data when layer toggled on
  useEffect(() => {
    if (eezLayerVisible && !eezData) {
      fetch('/data/eez_boundaries.geojson')
        .then((r) => r.json())
        .then(setEezData)
        .catch((e) => console.error('[Poseidon] Failed to load EEZ data:', e))
    }
  }, [eezLayerVisible, eezData, setEezData])

  // Load ports data when layer toggled on
  useEffect(() => {
    if (portsLayerVisible && !portsData) {
      fetch('/data/ports.geojson')
        .then((r) => r.json())
        .then(setPortsData)
        .catch((e) => console.error('[Poseidon] Failed to load ports data:', e))
    }
  }, [portsLayerVisible, portsData, setPortsData])

  // Load spoof heatmap data when toggled on
  useEffect(() => {
    if (spoofHeatmapVisible && spoofHeatmapData.length === 0) {
      fetchSpoofHeatmap(168).then(setSpoofHeatmapData).catch(console.error)
    }
  }, [spoofHeatmapVisible, spoofHeatmapData.length, setSpoofHeatmapData])

  // Load webcam data when layer toggled on
  useEffect(() => {
    if (webcamLayerVisible && webcamData.length === 0) {
      fetch((import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1/webcams')
        .then((r) => r.json())
        .then((d) => setWebcamData(d.webcams || []))
        .catch((e) => console.error('[Poseidon] Failed to load webcams:', e))
    }
  }, [webcamLayerVisible, webcamData.length])

  const handleClick = useCallback(
    async (info: PickingInfo) => {
      // AOI drawing mode: add points on click
      if (drawingAoi && info.coordinate) {
        setAoiPolygonPoints([...aoiPolygonPoints, [info.coordinate[0], info.coordinate[1]] as [number, number]])
        return
      }
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
    [setSelectedMmsi, setSelectedTrack, drawingAoi, aoiPolygonPoints, setAoiPolygonPoints],
  )

  const onViewStateChange = useCallback(
    ({ viewState: vs }: any) => setViewState(vs as MapViewState),
    [],
  )

  const getCursor = useCallback(
    ({ isHovering }: { isHovering: boolean }) => (drawingAoi ? 'crosshair' : isHovering ? 'pointer' : 'grab'),
    [drawingAoi],
  )

  // Pulsing effect for dark vessel alerts + ghost vessels + VIIRS + critical highlights
  const [pulsePhase, setPulsePhase] = useState(0)
  const hasGhosts = sarDetections.some((d) => !d.matched)
  const hasViirs = viirsAnomalies.length > 0 && viirsLayerVisible
  const hasCritical = criticalRiskMmsis.size > 0
  const hasSpoof = spoofClusters.length > 0 && spoofLayerVisible
  const hasAcoustic = acousticEvents.length > 0 && acousticLayerVisible
  const hasForensicFlagged = forensicPings.some((p) => p.flagged)
  useEffect(() => {
    if (darkAlerts.length === 0 && !hasGhosts && !hasViirs && !hasCritical && !hasSpoof && !hasAcoustic && !hasForensicFlagged) return
    const id = setInterval(() => setPulsePhase((p) => (p + 1) % 60), 50)
    return () => clearInterval(id)
  }, [darkAlerts.length, hasGhosts, hasViirs, hasCritical, hasSpoof, hasAcoustic, hasForensicFlagged])

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

  const spoofClusterLayer = useMemo(() => {
    if (!spoofLayerVisible || spoofClusters.length === 0) return null
    const pulseRadius = 10 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 5
    return new ScatterplotLayer<SpoofCluster>({
      id: 'spoof-clusters',
      data: spoofClusters,
      getPosition: (d) => [d.centroid_lon, d.centroid_lat],
      getFillColor: [255, 0, 255, 60],
      getLineColor: [255, 0, 255, 200],
      getRadius: pulseRadius,
      radiusMinPixels: pulseRadius,
      radiusMaxPixels: 24,
      stroked: true,
      lineWidthMinPixels: 2,
      radiusUnits: 'pixels',
      pickable: true,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [spoofClusters, spoofLayerVisible, pulsePhase])

  // Spoof heatmap layer
  const spoofHeatmap = useMemo(() => {
    if (!spoofHeatmapVisible || spoofHeatmapData.length === 0) return null
    return new HeatmapLayer<SpoofHeatmapPoint>({
      id: 'spoof-heatmap',
      data: spoofHeatmapData,
      getPosition: (d) => [d.lon, d.lat],
      getWeight: (d) => d.weight,
      radiusPixels: 60,
      intensity: 2,
      threshold: 0.1,
      colorRange: [
        [255, 255, 178],
        [254, 204, 92],
        [253, 141, 60],
        [240, 59, 32],
        [189, 0, 38],
        [128, 0, 38],
      ],
    })
  }, [spoofHeatmapVisible, spoofHeatmapData])

  // Shipping lane lines
  const shippingLanes = useMemo(() => maritimeData?.features?.filter((f: any) => f.properties?.type === 'lane'), [maritimeData])
  const chokepoints = useMemo(() => maritimeData?.features?.filter((f: any) => f.properties?.type === 'chokepoint'), [maritimeData])

  const shippingLaneLayer = useMemo(() => {
    if (!shippingLaneLayerVisible || !shippingLanes || shippingLanes.length === 0) return null
    return new GeoJsonLayer({
      id: 'shipping-lanes',
      data: { type: 'FeatureCollection', features: shippingLanes },
      getLineColor: [100, 180, 255, 80],
      getLineWidth: 2,
      lineWidthMinPixels: 1,
      lineWidthMaxPixels: 3,
      stroked: true,
      filled: false,
    })
  }, [shippingLaneLayerVisible, shippingLanes])

  const chokepointLayer = useMemo(() => {
    if (!shippingLaneLayerVisible || !chokepoints || chokepoints.length === 0) return null
    return new ScatterplotLayer({
      id: 'chokepoints',
      data: chokepoints,
      getPosition: (d: any) => d.geometry.coordinates,
      getFillColor: [255, 200, 80, 120],
      getLineColor: [255, 200, 80, 200],
      getRadius: 6,
      radiusMinPixels: 4,
      radiusMaxPixels: 10,
      stroked: true,
      lineWidthMinPixels: 1,
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [shippingLaneLayerVisible, chokepoints])

  const chokepointLabelLayer = useMemo(() => {
    if (!shippingLaneLayerVisible || !chokepoints || chokepoints.length === 0) return null
    return new TextLayer({
      id: 'chokepoint-labels',
      data: chokepoints,
      getPosition: (d: any) => d.geometry.coordinates,
      getText: (d: any) => d.properties.name,
      getSize: 11,
      getColor: [255, 200, 80, 180],
      getTextAnchor: 'start' as const,
      getAlignmentBaseline: 'center' as const,
      getPixelOffset: [10, 0],
      fontFamily: 'monospace',
      fontWeight: 'bold',
    })
  }, [shippingLaneLayerVisible, chokepoints])

  // EEZ boundary layer (blue polygons)
  const eezLayer = useMemo(() => {
    if (!eezLayerVisible || !eezData) return null
    return new GeoJsonLayer({
      id: 'eez-boundaries',
      data: eezData,
      getFillColor: [30, 80, 200, 15],
      getLineColor: [60, 130, 255, 120],
      lineWidthMinPixels: 1,
      lineWidthMaxPixels: 2,
      stroked: true,
      filled: true,
      pickable: true,
    })
  }, [eezLayerVisible, eezData])

  // Ports layer (teal dots)
  const portFeatures = useMemo(() => portsData?.features || [], [portsData])

  const portsLayer = useMemo(() => {
    if (!portsLayerVisible || portFeatures.length === 0) return null
    return new ScatterplotLayer({
      id: 'ports',
      data: portFeatures,
      getPosition: (d: any) => d.geometry.coordinates,
      getFillColor: (d: any) => {
        const size = d.properties.port_size
        return size === 'large' ? [0, 210, 180, 220] : size === 'medium' ? [0, 180, 160, 180] : [0, 150, 140, 140]
      },
      getRadius: (d: any) => (d.properties.port_size === 'large' ? 7 : d.properties.port_size === 'medium' ? 5 : 3),
      radiusMinPixels: 2,
      radiusMaxPixels: 10,
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [portsLayerVisible, portFeatures])

  // Port name labels (visible at zoom > 6)
  const portLabelLayer = useMemo(() => {
    if (!portsLayerVisible || portFeatures.length === 0 || viewState.zoom < 6) return null
    return new TextLayer({
      id: 'port-labels',
      data: portFeatures,
      getPosition: (d: any) => d.geometry.coordinates,
      getText: (d: any) => d.properties.name || '',
      getSize: 10,
      getColor: [0, 210, 180, 180],
      getTextAnchor: 'start' as const,
      getAlignmentBaseline: 'center' as const,
      getPixelOffset: [8, 0],
      fontFamily: 'monospace',
    })
  }, [portsLayerVisible, portFeatures, viewState.zoom])

  // Acoustic events layer (pulsing purple + bearing arcs)
  const acousticPointLayer = useMemo(() => {
    if (!acousticLayerVisible || acousticEvents.length === 0) return null
    const validEvents = acousticEvents.filter((e) => e.lon != null && e.lat != null)
    if (validEvents.length === 0) return null
    const pulseRadius = 7 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 3
    return new ScatterplotLayer<AcousticEvent>({
      id: 'acoustic-events',
      data: validEvents,
      getPosition: (d) => [d.lon!, d.lat!],
      getFillColor: [168, 85, 247, 160],
      getLineColor: [200, 120, 255, 220],
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
  }, [acousticLayerVisible, acousticEvents, pulsePhase])

  // Acoustic bearing arcs
  const acousticBearingLayer = useMemo(() => {
    if (!acousticLayerVisible || acousticEvents.length === 0) return null
    const withBearing = acousticEvents.filter((e) => e.lon != null && e.lat != null && e.bearing != null)
    if (withBearing.length === 0) return null
    return new ArcLayer({
      id: 'acoustic-bearings',
      data: withBearing,
      getSourcePosition: (d: AcousticEvent) => [d.lon!, d.lat!],
      getTargetPosition: (d: AcousticEvent) => {
        const dist = 1.0 // ~1 degree arc length
        const bearingRad = ((d.bearing || 0) * Math.PI) / 180
        return [d.lon! + dist * Math.sin(bearingRad), d.lat! + dist * Math.cos(bearingRad)]
      },
      getSourceColor: [168, 85, 247, 200],
      getTargetColor: [168, 85, 247, 40],
      getWidth: 2,
      greatCircle: false,
    })
  }, [acousticLayerVisible, acousticEvents])

  // Webcam marker layer (teal camera icons)
  const webcamMarkerLayer = useMemo(() => {
    if (!webcamLayerVisible || webcamData.length === 0) return null
    const validCams = webcamData.filter((c: any) => c.lon != null && c.lat != null)
    if (validCams.length === 0) return null
    return new ScatterplotLayer({
      id: 'webcam-markers',
      data: validCams,
      getPosition: (d: any) => [d.lon, d.lat],
      getFillColor: [0, 200, 180, 180],
      getLineColor: [0, 240, 210, 255],
      getRadius: 6,
      radiusMinPixels: 4,
      radiusMaxPixels: 10,
      stroked: true,
      lineWidthMinPixels: 1,
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [webcamLayerVisible, webcamData])

  // Webcam name labels (visible at zoom > 5)
  const webcamLabelLayer = useMemo(() => {
    if (!webcamLayerVisible || webcamData.length === 0 || viewState.zoom < 5) return null
    const validCams = webcamData.filter((c: any) => c.lon != null && c.lat != null)
    if (validCams.length === 0) return null
    return new TextLayer({
      id: 'webcam-labels',
      data: validCams,
      getPosition: (d: any) => [d.lon, d.lat],
      getText: (d: any) => d.name || '',
      getSize: 10,
      getColor: [0, 200, 180, 180],
      getTextAnchor: 'start' as const,
      getAlignmentBaseline: 'center' as const,
      getPixelOffset: [10, 0],
      fontFamily: 'monospace',
    })
  }, [webcamLayerVisible, webcamData, viewState.zoom])

  // Forensic pings layer (green clean, orange/red flagged)
  const forensicPingLayer = useMemo(() => {
    if (!selectedMmsi || forensicPings.length === 0) return null
    const pulseRadius = 4 + (hasForensicFlagged ? Math.sin((pulsePhase / 60) * Math.PI * 2) * 2 : 0)
    return new ScatterplotLayer<ForensicPing>({
      id: 'forensic-pings',
      data: forensicPings,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => d.flagged ? [255, 120, 0, 200] : [0, 220, 100, 180],
      getLineColor: (d) => d.flagged ? [255, 60, 0, 255] : [0, 180, 80, 200],
      getRadius: (d) => d.flagged ? pulseRadius : 4,
      radiusMinPixels: 3,
      radiusMaxPixels: 10,
      stroked: true,
      lineWidthMinPixels: 1,
      radiusUnits: 'pixels',
      pickable: true,
      updateTriggers: {
        getRadius: pulsePhase,
      },
    })
  }, [selectedMmsi, forensicPings, pulsePhase, hasForensicFlagged])

  // Forensic track path (connect pings chronologically)
  const forensicTrackLayer = useMemo(() => {
    if (!selectedMmsi || forensicPings.length < 2) return null
    const sorted = [...forensicPings].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    return new PathLayer({
      id: 'forensic-track',
      data: [{ path: sorted.map((p) => [p.lon, p.lat]) }],
      getPath: (d: any) => d.path,
      getColor: [255, 180, 0, 100],
      getWidth: 1.5,
      widthMinPixels: 1,
      widthMaxPixels: 3,
      jointRounded: true,
      capRounded: true,
    })
  }, [selectedMmsi, forensicPings])

  // Destination marker (star icon via ScatterplotLayer)
  const destinationMarkerLayer = useMemo(() => {
    if (!routeLayerVisible || !routePrediction?.destination_coords) return null
    return new ScatterplotLayer({
      id: 'destination-marker',
      data: [{ position: routePrediction.destination_coords, name: routePrediction.destination_name }],
      getPosition: (d: any) => d.position,
      getFillColor: [0, 255, 255, 200],
      getLineColor: [0, 200, 255, 255],
      getRadius: 8,
      radiusMinPixels: 6,
      radiusMaxPixels: 14,
      stroked: true,
      lineWidthMinPixels: 2,
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [routeLayerVisible, routePrediction])

  // Destination route line (cyan dashed from vessel to destination port)
  const destinationRouteLayer = useMemo(() => {
    if (!routeLayerVisible || !routePrediction?.destination_coords || !routePrediction.route_geom?.length) return null
    const start = routePrediction.route_geom[0]
    return new PathLayer({
      id: 'destination-route',
      data: [{ path: [start, routePrediction.destination_coords] }],
      getPath: (d: any) => d.path,
      getColor: [0, 220, 255, 160],
      getWidth: 2,
      widthMinPixels: 2,
      widthMaxPixels: 4,
      getDashArray: [8, 6],
      dashJustified: true,
      jointRounded: true,
      capRounded: true,
    })
  }, [routeLayerVisible, routePrediction])

  // Destination label
  const destinationLabelLayer = useMemo(() => {
    if (!routeLayerVisible || !routePrediction?.destination_coords || !routePrediction.destination_name) return null
    return new TextLayer({
      id: 'destination-label',
      data: [{ position: routePrediction.destination_coords, name: routePrediction.destination_name }],
      getPosition: (d: any) => d.position,
      getText: (d: any) => d.name,
      getSize: 12,
      getColor: [0, 255, 255, 220],
      getTextAnchor: 'start' as const,
      getAlignmentBaseline: 'center' as const,
      getPixelOffset: [12, 0],
      fontFamily: 'monospace',
      fontWeight: 'bold',
    })
  }, [routeLayerVisible, routePrediction])

  // AOI saved polygon layer
  const aoiLayer = useMemo(() => {
    if (aoiGeoJsons.length === 0) return null
    return new GeoJsonLayer({
      id: 'aoi-polygons',
      data: { type: 'FeatureCollection', features: aoiGeoJsons.map((g, i) => ({ ...g, properties: { ...g?.properties, _idx: i } })) },
      getFillColor: [0, 200, 180, 25],
      getLineColor: [0, 200, 180, 140],
      lineWidthMinPixels: 2,
      stroked: true,
      filled: true,
    })
  }, [aoiGeoJsons])

  // AOI drawing polygon (in-progress)
  const aoiDrawingLayer = useMemo(() => {
    if (!drawingAoi || aoiPolygonPoints.length === 0) return null
    if (aoiPolygonPoints.length < 3) {
      // Show as path while fewer than 3 points
      return new PathLayer({
        id: 'aoi-drawing-path',
        data: [{ path: aoiPolygonPoints }],
        getPath: (d: any) => d.path,
        getColor: [0, 255, 200, 200],
        getWidth: 2,
        widthMinPixels: 2,
      })
    }
    return new PolygonLayer({
      id: 'aoi-drawing-polygon',
      data: [{ polygon: aoiPolygonPoints }],
      getPolygon: (d: any) => d.polygon,
      getFillColor: [0, 255, 200, 40],
      getLineColor: [0, 255, 200, 200],
      lineWidthMinPixels: 2,
      stroked: true,
      filled: true,
    })
  }, [drawingAoi, aoiPolygonPoints])

  // AOI drawing point markers
  const aoiDrawingPointsLayer = useMemo(() => {
    if (!drawingAoi || aoiPolygonPoints.length === 0) return null
    return new ScatterplotLayer({
      id: 'aoi-drawing-points',
      data: aoiPolygonPoints.map((p, i) => ({ position: p, index: i })),
      getPosition: (d: any) => d.position,
      getFillColor: [0, 255, 200, 255],
      getRadius: 5,
      radiusMinPixels: 5,
      radiusUnits: 'pixels',
    })
  }, [drawingAoi, aoiPolygonPoints])

  const layers = useMemo(
    () => [spoofHeatmap, eezLayer, confidenceConeLayer, shippingLaneLayer, chokepointLayer, chokepointLabelLayer, aoiLayer, aoiDrawingLayer, aoiDrawingPointsLayer, portsLayer, portLabelLayer, webcamMarkerLayer, webcamLabelLayer, vesselLayer, criticalHighlightLayer, trackLayer, forensicTrackLayer, forensicPingLayer, routePredictionLayer, destinationRouteLayer, destinationMarkerLayer, destinationLabelLayer, darkAlertsLayer, sarDetectionLayer, ghostVesselLayer, viirsLayer, spoofClusterLayer, acousticPointLayer, acousticBearingLayer].filter(Boolean),
    [spoofHeatmap, eezLayer, confidenceConeLayer, shippingLaneLayer, chokepointLayer, chokepointLabelLayer, aoiLayer, aoiDrawingLayer, aoiDrawingPointsLayer, portsLayer, portLabelLayer, webcamMarkerLayer, webcamLabelLayer, vesselLayer, criticalHighlightLayer, trackLayer, forensicTrackLayer, forensicPingLayer, routePredictionLayer, destinationRouteLayer, destinationMarkerLayer, destinationLabelLayer, darkAlertsLayer, sarDetectionLayer, ghostVesselLayer, viirsLayer, spoofClusterLayer, acousticPointLayer, acousticBearingLayer],
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
        >
          {/* GEBCO Bathymetry raster overlay */}
          {bathymetryLayerVisible && (
            <Source
              id="gebco-bathymetry"
              type="raster"
              tiles={[GEBCO_WMS_URL]}
              tileSize={256}
            >
              <MapLayer
                id="gebco-bathymetry-layer"
                type="raster"
                paint={{ 'raster-opacity': 0.4 }}
              />
            </Source>
          )}
        </Map>
      </DeckGL>
    </div>
  )
}
