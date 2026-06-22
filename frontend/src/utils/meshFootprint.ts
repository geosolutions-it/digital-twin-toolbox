export type MapBbox = [number, number, number, number]

const METERS_PER_DEGREE_LAT = 111_320

export function parseMeshSize(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null
  }
  const width = Number(value[0])
  const depth = Number(value[1])
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(depth) ||
    width <= 0 ||
    depth <= 0
  ) {
    return null
  }
  return [width, depth]
}

/** Ground footprint [west, south, east, north] with lat/lon at horizontal mesh center. */
export function computeMeshFootprintBboxFromDimensions(
  latitude: number,
  longitude: number,
  widthMeters: number,
  depthMeters: number,
): MapBbox | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null
  }
  if (widthMeters <= 0 || depthMeters <= 0) {
    return null
  }

  const metersPerDegreeLon =
    METERS_PER_DEGREE_LAT * Math.cos((latitude * Math.PI) / 180)
  const halfLon = widthMeters / 2 / metersPerDegreeLon
  const halfLat = depthMeters / 2 / METERS_PER_DEGREE_LAT

  return [
    longitude - halfLon,
    latitude - halfLat,
    longitude + halfLon,
    latitude + halfLat,
  ]
}
