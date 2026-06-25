import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import { useEffect, useRef } from "react"
import { buildMapLibreBasemapStyle } from "../../utils/mapBasemap"
import {
  type MapBbox,
  computeMeshFootprintBboxFromDimensions,
  parseMeshOffset,
  parseMeshSize,
} from "../../utils/meshFootprint"

const BASEMAP_STYLE = buildMapLibreBasemapStyle()

const FOOTPRINT_SOURCE = "mesh-footprint"
const FOOTPRINT_FILL = "mesh-footprint-fill"
const FOOTPRINT_OUTLINE = "mesh-footprint-outline"

const LOCATION_ZOOM = 14

interface MeshMapPickerProps {
  className?: string
  style?: React.CSSProperties
  latitude: number
  longitude: number
  onLocationChange: (latitude: number, longitude: number) => void
  meshSizeMeters?: number[] | null
  meshOffsetMeters?: number[] | null
  /** Increment to fly the map to the current latitude/longitude. */
  zoomToLocationKey?: number
}

function bboxToFeatureCollection(
  bbox: MapBbox | null,
): GeoJSON.FeatureCollection {
  if (!bbox) {
    return { type: "FeatureCollection", features: [] }
  }
  const [west, south, east, north] = bbox
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
        properties: {},
      },
    ],
  }
}

function hasCoordinates(latitude: number, longitude: number): boolean {
  return latitude !== 0 || longitude !== 0
}

/** MapLibre picker for mesh pipeline - draggable marker and footprint bbox. */
function MeshMapPicker({
  latitude,
  longitude,
  onLocationChange,
  meshSizeMeters = null,
  meshOffsetMeters = null,
  zoomToLocationKey = 0,
  className,
  style,
}: MeshMapPickerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const isDraggingRef = useRef(false)
  const onLocationChangeRef = useRef(onLocationChange)
  onLocationChangeRef.current = onLocationChange

  const initialLatitudeRef = useRef(latitude)
  const initialLongitudeRef = useRef(longitude)
  const latitudeRef = useRef(latitude)
  const longitudeRef = useRef(longitude)
  latitudeRef.current = latitude
  longitudeRef.current = longitude

  const meshDimensions = parseMeshSize(meshSizeMeters)
  const meshOffset = parseMeshOffset(meshOffsetMeters)
  const footprintBbox =
    meshDimensions === null
      ? null
      : computeMeshFootprintBboxFromDimensions(
          latitude,
          longitude,
          meshDimensions[0],
          meshDimensions[1],
          meshOffset?.[0] ?? 0,
          meshOffset?.[1] ?? 0,
        )
  const footprintBboxRef = useRef(footprintBbox)
  footprintBboxRef.current = footprintBbox
  const footprintKey = footprintBbox
    ? footprintBbox.map((value) => value.toFixed(8)).join(",")
    : ""

  const applyFootprintToMap = (map: maplibregl.Map) => {
    const source = map.getSource(FOOTPRINT_SOURCE) as
      | maplibregl.GeoJSONSource
      | undefined
    if (!source) {
      return
    }
    source.setData(bboxToFeatureCollection(footprintBboxRef.current))
  }

  const flyToLocation = (map: maplibregl.Map) => {
    const lat = latitudeRef.current
    const lon = longitudeRef.current
    if (!hasCoordinates(lat, lon)) {
      return
    }
    map.flyTo({
      center: [lon, lat],
      zoom: LOCATION_ZOOM,
      essential: true,
      duration: 0,
    })
  }

  useEffect(() => {
    const container = containerRef.current
    if (!container || mapRef.current) {
      return
    }

    const initialLat = initialLatitudeRef.current
    const initialLon = initialLongitudeRef.current

    const map = new maplibregl.Map({
      container,
      style: BASEMAP_STYLE,
      center: hasCoordinates(initialLat, initialLon)
        ? [initialLon, initialLat]
        : [0, 0],
      zoom: hasCoordinates(initialLat, initialLon) ? 14 : 2,
      attributionControl: { compact: true },
    })

    map.addControl(new maplibregl.NavigationControl(), "top-right")
    mapRef.current = map

    map.on("load", () => {
      map.addSource(FOOTPRINT_SOURCE, {
        type: "geojson",
        data: bboxToFeatureCollection(null),
      })
      map.addLayer({
        id: FOOTPRINT_FILL,
        type: "fill",
        source: FOOTPRINT_SOURCE,
        paint: {
          "fill-color": "#3182ce",
          "fill-opacity": 0.2,
        },
      })
      map.addLayer({
        id: FOOTPRINT_OUTLINE,
        type: "line",
        source: FOOTPRINT_SOURCE,
        paint: {
          "line-color": "#2b6cb0",
          "line-width": 2,
        },
      })

      const marker = new maplibregl.Marker({ draggable: true, color: "#e53e3e" })
        .setLngLat([longitudeRef.current, latitudeRef.current])
        .addTo(map)

      marker.on("dragstart", () => {
        isDraggingRef.current = true
      })
      marker.on("dragend", () => {
        isDraggingRef.current = false
        const { lat, lng } = marker.getLngLat()
        onLocationChangeRef.current(lat, lng)
      })

      markerRef.current = marker
      applyFootprintToMap(map)
    })

    const resizeObserver = new ResizeObserver(() => {
      map.resize()
    })
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      markerRef.current?.remove()
      markerRef.current = null
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!markerRef.current || isDraggingRef.current) {
      return
    }
    markerRef.current.setLngLat([longitude, latitude])
  }, [latitude, longitude])

  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }
    applyFootprintToMap(map)
  }, [footprintKey, footprintBbox])

  useEffect(() => {
    if (!zoomToLocationKey) {
      return
    }
    const map = mapRef.current
    if (!map) {
      return
    }
    flyToLocation(map)
  }, [zoomToLocationKey])

  return (
    <div
      ref={containerRef}
      role="application"
      aria-label="Mesh map picker"
      className={className}
      style={{ position: "absolute", inset: 0, ...style }}
    />
  )
}

export default MeshMapPicker
