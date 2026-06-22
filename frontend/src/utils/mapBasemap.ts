import type { StyleSpecification } from "maplibre-gl"

export const OSM_BASEMAP = {
  format: "image/jpeg",
  name: "osm:osm",
  url: [
    "https://maps1.geosolutionsgroup.com/geoserver/wms",
    "https://maps2.geosolutionsgroup.com/geoserver/wms",
    "https://maps3.geosolutionsgroup.com/geoserver/wms",
    "https://maps4.geosolutionsgroup.com/geoserver/wms",
    "https://maps5.geosolutionsgroup.com/geoserver/wms",
    "https://maps6.geosolutionsgroup.com/geoserver/wms",
  ],
  tileSize: 512,
  attribution:
    "OSM Bright | GeoSolutions | © OpenStreetMap contributors, ODbL",
} as const

function buildWmsTileUrl(
  wmsBaseUrl: string,
  layerName: string,
  format: string,
  tileSize: number,
): string {
  const query = [
    "SERVICE=WMS",
    "VERSION=1.1.1",
    "REQUEST=GetMap",
    `FORMAT=${encodeURIComponent(format)}`,
    "TRANSPARENT=false",
    `LAYERS=${encodeURIComponent(layerName)}`,
    "STYLES=",
    "SRS=EPSG:3857",
    `WIDTH=${tileSize}`,
    `HEIGHT=${tileSize}`,
    "bbox={bbox-epsg-3857}",
  ].join("&")

  return `${wmsBaseUrl}?${query}`
}

export function buildMapLibreBasemapStyle(): StyleSpecification {
  const { url, name, format, tileSize, attribution } = OSM_BASEMAP
  const tiles = url.map((wmsBaseUrl) =>
    buildWmsTileUrl(wmsBaseUrl, name, format, tileSize),
  )
  const sourceId = "mapstore-osm-bright"

  return {
    version: 8,
    sources: {
      [sourceId]: {
        type: "raster",
        tiles,
        tileSize,
        attribution,
      },
    },
    layers: [
      {
        id: "mapstore-osm-bright-raster",
        type: "raster",
        source: sourceId,
      },
    ],
  }
}
