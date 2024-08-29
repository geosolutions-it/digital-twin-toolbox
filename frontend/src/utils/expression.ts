const getFunc = (name: string, feature: any) => {
  if (["$maxZ", "$minZ"].includes(name)) {
    if (feature.geometry.type === "Point") {
      return feature.geometry.coordinates[2] || 0
    }
    if (feature.geometry.type === "Polygon") {
      let minZ = Number.POSITIVE_INFINITY
      let maxZ = Number.NEGATIVE_INFINITY
      for (let i = 0; i < feature.geometry.coordinates.length; i++) {
        const ring = feature.geometry.coordinates[i]
        for (let y = 0; y < ring.length; y++) {
          const coords = ring[y]
          const z = coords[2] || 0
          if (z < minZ) {
            minZ = z
          }
          if (z > maxZ) {
            maxZ = z
          }
        }
      }
      return name === "$maxZ" ? maxZ : minZ
    }
  }
  return null
}

export const parseExpression = (
  type: string,
  value: any,
  feature: any,
): any => {
  if (value === "" || value === undefined) {
    return undefined
  }
  if (!Array.isArray(value)) {
    if (type === "string") {
      return `${value}`
    }
    if (type === "number") {
      return Number.parseFloat(value)
    }
    return value
  }
  const [operator, ...args] = value
  const _type = ["property", "func"].includes(operator) ? "" : type
  const a: any = args?.[0]
    ? parseExpression(_type, args[0], feature)
    : undefined
  const b: any = args?.[1]
    ? parseExpression(_type, args[1], feature)
    : undefined
  switch (operator) {
    case "+":
      return a + b
    case "-":
      return a - b
    case "*":
      return a * b
    case "/":
      return a / b
    case "concat":
      return `${a}${b}`
    case "lowercase":
      return `${a}`.toLowerCase()
    case "uppercase":
      return `${a}`.toUpperCase()
    case "property":
      return feature?.properties?.[a]
    case "func":
      return getFunc(a, feature)
    default:
      return null
  }
}
