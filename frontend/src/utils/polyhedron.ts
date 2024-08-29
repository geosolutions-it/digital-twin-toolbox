import earcut from "earcut"
import { convertToCartesian } from "./cartesian"

const parseCoords = (
  coords: number[],
  z: number | undefined,
  translateZ: number | undefined,
) => [
  coords[0],
  coords[1],
  (z !== undefined ? z : coords[2] || 0) + (translateZ || 0),
]

const parseRing = (
  ring: number[][],
  z: number | undefined,
  translateZ: number | undefined,
) => ring.map((coords: number[]) => parseCoords(coords, z, translateZ))

const sumUntilIndex = (arr: number[], index: number) =>
  arr
    // @ts-ignore
    .filter((value: number, idx: number) => idx < index)
    .reduce((sum: number, value: number) => sum + value, 0)

const triangulate = (coordinates: number[][][], reverse: boolean) => {
  const holes = coordinates
    // @ts-ignore
    .filter((coords, idx: number) => idx !== 0)
    .flatMap((c) => c.flat())
  const holesIndices = coordinates
    // @ts-ignore
    .map((coords, idx) =>
      coordinates[idx - 1] ? coordinates[idx - 1].length : null,
    )
    .filter((value) => value !== null)
    .map((value, idx, arr) => value + sumUntilIndex(arr, idx))
  const outer = coordinates[0].flat()
  const merged = [...outer, ...holes]
  const indices = earcut(merged, holesIndices, 3)
  const vertices = coordinates.flat()
  const polyhedron = []
  for (let i = 0; i < indices.length; i += 3) {
    polyhedron.push([
      convertToCartesian(vertices[indices[i]]),
      convertToCartesian(vertices[indices[i + (reverse ? 2 : 1)]]),
      convertToCartesian(vertices[indices[i + (reverse ? 1 : 2)]]),
      convertToCartesian(vertices[indices[i]]),
    ])
  }
  return polyhedron
}

const planeToWall = (lowerRing: number[][], upperRing: number[][]) => {
  const polyhedron = []
  for (let i = 0; i < lowerRing.length - 1; i++) {
    if (lowerRing[i + 1]) {
      const bl = convertToCartesian(lowerRing[i])
      const br = convertToCartesian(lowerRing[i + 1])
      const tl = convertToCartesian(upperRing[i])
      const tr = convertToCartesian(upperRing[i + 1])
      polyhedron.push([bl, tl, br, bl])
      polyhedron.push([br, tl, tr, br])
    }
  }
  return polyhedron
}

const generateWalls = (lower: number[][][], upper: number[][][]) => {
  // @ts-ignore
  return lower.flatMap((ring, idx) => {
    return planeToWall(lower[idx], upper[idx])
  })
}
const toPolyhedralSurface = (
  // @ts-ignore
  feature: any,
  [lower, upper]: number[][][][],
  removeBottomSurface: boolean | undefined,
) => {
  if (upper === undefined) {
    return triangulate(lower, false)
  }
  return [
    ...triangulate(upper, false),
    ...generateWalls(lower, upper),
    ...(removeBottomSurface ? [] : triangulate(lower, true)),
  ]
}

interface ParsersOptions {
  lowerLimit: number | undefined
  upperLimit: number | undefined
  translateZ: number | undefined
  removeBottomSurface: boolean | undefined
}

const parsers: any = {
  Polygon: (feature: any, options: ParsersOptions) => {
    const { lowerLimit, upperLimit, translateZ, removeBottomSurface } =
      options || {}
    if (lowerLimit === undefined && upperLimit === undefined) {
      const lower = feature.geometry.coordinates.map((ring: number[][]) =>
        parseRing(ring, lowerLimit, translateZ),
      )
      return toPolyhedralSurface(feature, [lower], removeBottomSurface)
    }
    const lower = feature.geometry.coordinates.map((ring: number[][]) =>
      parseRing(ring, lowerLimit, translateZ),
    )
    const upper = feature.geometry.coordinates.map((ring: number[][]) =>
      parseRing(ring, upperLimit, translateZ),
    )
    const averageZLower =
      lower[0].reduce((sum: number, coords: number[]) => sum + coords[2], 0) /
      lower[0].length
    const averageZUpper =
      upper[0].reduce((sum: number, coords: number[]) => sum + coords[2], 0) /
      upper[0].length
    return toPolyhedralSurface(
      feature,
      averageZLower > averageZUpper ? [upper, lower] : [lower, upper],
      removeBottomSurface,
    )
  },
  MultiPolygon: (feature: any, options: ParsersOptions) => {
    return feature.geometry.coordinates.flatMap(
      (coordinates: number[][][][]) => {
        return parsers.Polygon(
          { ...feature, geometry: { type: "Polygon", coordinates } },
          options,
        )
      },
    )
  },
}

export const collectionToPolyhedralSurfaceZ = (
  collection: any,
  {
    filter = (feature: any) => feature,
    // @ts-ignore
    computeOptions = (feature: any) => ({
      lowerLimit: undefined,
      upperLimit: undefined,
      translateZ: undefined,
      removeBottomSurface: true,
    }),
  } = {},
) => {
  if (!collection?.features) {
    return {
      type: "FeatureCollection",
      features: [],
    }
  }
  const features = collection.features.filter(filter).map((feature: any) => {
    const options = computeOptions(feature)
    const coordinates = parsers[feature.geometry.type](feature, options)
    return {
      ...feature,
      geometry: {
        type: "POLYHEDRALSURFACE Z",
        coordinates,
      },
    }
  })
  return {
    type: "FeatureCollection",
    features,
  }
}
