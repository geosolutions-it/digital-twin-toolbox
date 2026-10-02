import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import { useEffect, useRef } from "react"
import { buildMapLibreBasemapStyle } from "../../utils/mapBasemap"
import {
  type MapBbox,
  bboxToFeatureCollection,
} from "../../utils/mapBBox"

const BASEMAP_STYLE = buildMapLibreBasemapStyle()

const FOOTPRINT_SOURCE = "bbox-footprint"
const FOOTPRINT_FILL = "bbox-footprint-fill"
const FOOTPRINT_OUTLINE = "bbox-footprint-outline"

interface MapBBoxViewerProps {
  bbox?: MapBbox | null
  className?: string
  style?: React.CSSProperties
}

/** Read-only MapLibre viewer that displays a WGS84 bounding box. */
function MapBBoxViewer({ bbox = null, className, style }: MapBBoxViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const bboxRef = useRef(bbox)
  bboxRef.current = bbox
  const bboxKey = bbox ? bbox.map((value) => value.toFixed(8)).join(",") : ""

  const applyBboxToMap = (map: maplibregl.Map) => {
    const source = map.getSource(FOOTPRINT_SOURCE) as
      | maplibregl.GeoJSONSource
      | undefined
    if (!source) {
      return
    }
    source.setData(bboxToFeatureCollection(bboxRef.current))
    const currentBbox = bboxRef.current
    if (!currentBbox) {
      return
    }
    const [west, south, east, north] = currentBbox
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 48, duration: 0, maxZoom: 17 },
    )
  }

  useEffect(() => {
    const container = containerRef.current
    if (!container || mapRef.current) {
      return
    }

    const map = new maplibregl.Map({
      container,
      style: BASEMAP_STYLE,
      center: [0, 0],
      zoom: 2,
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
      applyBboxToMap(map)
    })

    const resizeObserver = new ResizeObserver(() => {
      map.resize()
    })
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    applyBboxToMap(map)
  }, [bboxKey, bbox])

  return (
    <div
      ref={containerRef}
      role="application"
      aria-label="Dataset location preview"
      className={className}
      style={{ position: "absolute", inset: 0, ...style }}
    />
  )
}

export default MapBBoxViewer
