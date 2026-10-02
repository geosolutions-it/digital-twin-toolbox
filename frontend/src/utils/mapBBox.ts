export type MapBbox = [number, number, number, number]

export function bboxToFeatureCollection(
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

export function parseWgs84Bbox(value: unknown): MapBbox | null {
  if (!Array.isArray(value) || value.length < 4) {
    return null
  }
  const bbox = value.slice(0, 4).map((entry) => Number(entry))
  if (bbox.some((entry) => Number.isNaN(entry))) {
    return null
  }
  return bbox as MapBbox
}
