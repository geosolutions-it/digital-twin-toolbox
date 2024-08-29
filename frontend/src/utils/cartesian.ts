import { Euler, Quaternion, Vector3 } from "three"

// https://github.com/CesiumGS/cesium/blob/1.120/packages/engine/Source/Core/Math.js#L438
const RADIANS_PER_DEGREE = Math.PI / 180.0
const toRadians = (degrees: number) => degrees * RADIANS_PER_DEGREE

const radiiSquared = [
  6378137.0 * 6378137.0,
  6378137.0 * 6378137.0,
  6356752.3142451793 * 6356752.3142451793,
]

// extracted from https://github.com/mrdoob/three.js/blob/dev/src/math/Vector3.js
const vectorLength = ([x, y, z]: number[]) => x * x + y * y + z * z
const vectorMultiplyScalar = ([x, y, z]: number[], scalar: number) => [
  x * scalar,
  y * scalar,
  z * scalar,
]
const vectorDivideScalar = (vector: number[], scalar: number) =>
  vectorMultiplyScalar(vector, 1 / scalar)
const vectorNormalize = (vector: number[]) =>
  vectorDivideScalar(vector, vectorLength(vector) || 1)
const vectorAdd = (a: number[], b: number[]) => [
  a[0] + b[0],
  a[1] + b[1],
  a[2] + b[2],
]
const vectorMultiply = (a: number[], b: number[]) => [
  a[0] * b[0],
  a[1] * b[1],
  a[2] * b[2],
]
const vectorDot = (a: number[], b: number[]) =>
  a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
// https://github.com/CesiumGS/cesium/blob/1.120/packages/engine/Source/Core/Cartesian3.js#L876
const fromRadians = (longitude: number, latitude: number, height: number) => {
  const cosLatitude = Math.cos(latitude)
  const x = cosLatitude * Math.cos(longitude)
  const y = cosLatitude * Math.sin(longitude)
  const z = Math.sin(latitude)

  const normalized = vectorNormalize([x, y, z])
  const k = vectorMultiply(radiiSquared, normalized)
  const gamma = Math.sqrt(vectorDot(normalized, k))

  const output = vectorAdd(
    vectorDivideScalar(k, gamma),
    vectorMultiplyScalar(normalized, height),
  )
  return output
}

export const convertToCartesian = ([longitude, latitude, height]: number[]) => {
  return fromRadians(toRadians(longitude), toRadians(latitude), height || 0)
}

// from  https://stackoverflow.com/a/52978898
const computeCartesianEuler = (cartesian: number[]) => {
  // Set starting and ending vectors
  const myVector = new Vector3(...cartesian)
  const targetVector = new Vector3(0, 0, 1)

  // Normalize vectors to make sure they have a length of 1
  myVector.normalize()
  targetVector.normalize()

  // Create a quaternion, and apply starting, then ending vectors
  const quaternion = new Quaternion()
  quaternion.setFromUnitVectors(myVector, targetVector)

  // Quaternion now has rotation data within it.
  // We'll need to get it out with a THREE.Euler()
  const euler = new Euler()
  euler.setFromQuaternion(quaternion)
  return euler
}

export const translateAndRotate = (
  [x, y, z]: number[],
  translate: number[],
) => {
  const vector = new Vector3(
    x - translate[0],
    y - translate[1],
    z - translate[2],
  )
  const euler = computeCartesianEuler([x, y, z])
  vector.applyEuler(euler)
  vector.applyEuler(new Euler(-Math.PI / 2, 0, -Math.PI / 2))
  return [vector.x, vector.y, vector.z]
}
