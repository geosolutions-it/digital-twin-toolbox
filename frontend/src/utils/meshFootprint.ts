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

export type AxisOption = "X" | "Y" | "Z" | "NEGATIVE_X" | "NEGATIVE_Y" | "NEGATIVE_Z"

const AXIS_VECTORS: Record<AxisOption, [number, number, number]> = {
  X: [1, 0, 0],
  Y: [0, 1, 0],
  Z: [0, 0, 1],
  NEGATIVE_X: [-1, 0, 0],
  NEGATIVE_Y: [0, -1, 0],
  NEGATIVE_Z: [0, 0, -1],
}

type Vec3 = [number, number, number]

export function parseVec3(value: unknown): Vec3 | null {
  if (!Array.isArray(value) || value.length < 3) {
    return null
  }
  const a = Number(value[0])
  const b = Number(value[1])
  const c = Number(value[2])
  if (!Number.isFinite(a) || !Number.isFinite(b) || !Number.isFinite(c)) {
    return null
  }
  return [a, b, c]
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]

/**
 * Reorient a file-axis bbox into the ENU frame (x=east, y=north, z=up) that the
 * Blender import produces for the given forward/up axes. forward='Y', up='Z'
 * is identity. forward and up must be orthogonal; otherwise returns input as-is.
 */
export function reorientMeshBbox(
  size: Vec3,
  offset: Vec3,
  forwardAxis: AxisOption,
  upAxis: AxisOption,
): { size: Vec3; offset: Vec3 } {
  const fwd = AXIS_VECTORS[forwardAxis]
  const up = AXIS_VECTORS[upAxis]
  const right = cross(fwd, up) // -> east (x)
  if (dot(right, right) === 0) {
    return { size, offset }
  }
  // rows X=right, Y=fwd, Z=up; size keeps magnitudes, offset keeps sign
  const project = (axis: Vec3): number =>
    Math.abs(axis[0]) * size[0] +
    Math.abs(axis[1]) * size[1] +
    Math.abs(axis[2]) * size[2]
  return {
    size: [project(right), project(fwd), project(up)],
    offset: [dot(right, offset), dot(fwd, offset), dot(up, offset)],
  }
}

/** Offset [east, north] of the bbox center vs the model origin (0,0,0), in meters. */
export function parseMeshOffset(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null
  }
  const east = Number(value[0])
  const north = Number(value[1])
  if (!Number.isFinite(east) || !Number.isFinite(north)) {
    return null
  }
  return [east, north]
}

/**
 * Ground footprint [west, south, east, north]. lat/lon is the model origin
 * (0,0,0); the box is shifted by offset [east, north] (m) to its true position.
 */
export function computeMeshFootprintBboxFromDimensions(
  latitude: number,
  longitude: number,
  widthMeters: number,
  depthMeters: number,
  offsetEastMeters = 0,
  offsetNorthMeters = 0,
): MapBbox | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null
  }
  if (widthMeters <= 0 || depthMeters <= 0) {
    return null
  }

  const metersPerDegreeLon =
    METERS_PER_DEGREE_LAT * Math.cos((latitude * Math.PI) / 180)
  const centerLon = longitude + offsetEastMeters / metersPerDegreeLon
  const centerLat = latitude + offsetNorthMeters / METERS_PER_DEGREE_LAT
  const halfLon = widthMeters / 2 / metersPerDegreeLon
  const halfLat = depthMeters / 2 / METERS_PER_DEGREE_LAT

  return [
    centerLon - halfLon,
    centerLat - halfLat,
    centerLon + halfLon,
    centerLat + halfLat,
  ]
}
