import { Box, IconButton, Text, Tooltip, VStack } from "@chakra-ui/react"
import * as Cesium from "cesium"
import { useEffect, useMemo, useRef, useState } from "react"
import { FiCrosshair } from "react-icons/fi"
import type { MeshBbox, SampleFeature } from "../../api/pipelineBatch"
import { modelUrl } from "../../api/storageBrowser"
import { createViewer } from "../../utils/cesium"
import { type ExprType, evaluate } from "../../utils/expression"
import { isInvalidExpression } from "./ExpressionInput"

export type PreviewKind = "Polygon" | "Instance" | "Mesh"

interface PreviewMapProps {
  kind: PreviewKind
  values: Record<string, any>
  features?: SampleFeature[]
  bbox?: MeshBbox
  status?: string
  onPick?: (lat: number, lon: number) => void
}

const FILL = Cesium.Color.fromCssColorString("#4f9dde").withAlpha(0.85)
const EDGE = Cesium.Color.WHITE.withAlpha(0.5)
const MESH_FILL = Cesium.Color.fromCssColorString("#f6ad55").withAlpha(0.35)
const MESH_EDGE = Cesium.Color.fromCssColorString("#dd6b20")
const MISSING = Cesium.Color.fromCssColorString("#e53e3e")
const AXIS_VECTORS: Record<string, number[]> = {
  X: [1, 0, 0],
  Y: [0, 1, 0],
  Z: [0, 0, 1],
  NEGATIVE_X: [-1, 0, 0],
  NEGATIVE_Y: [0, -1, 0],
  NEGATIVE_Z: [0, 0, -1],
}
const METERS_PER_DEGREE = 111_320

/** As in the worker: no value, an error or non-finite means the default. */
function evalOr(
  type: ExprType,
  expr: unknown,
  feature: SampleFeature,
  fallback: any,
) {
  if (expr === undefined || expr === null || expr === "") return fallback
  try {
    const v = evaluate(type, expr, feature)
    if (
      v === null ||
      v === undefined ||
      (typeof v === "number" && !Number.isFinite(v))
    )
      return fallback
    return v
  } catch {
    return fallback
  }
}

function polygonParts(feature: SampleFeature): number[][][][] {
  const g = feature.geometry
  if (g?.type === "Polygon") return [g.coordinates]
  if (g?.type === "MultiPolygon") return g.coordinates
  return []
}

const ringPositions = (ring: number[][]) =>
  Cesium.Cartesian3.fromDegreesArray(ring.flatMap((c) => [c[0], c[1]]))

/** ENU extent of the mesh bbox; mirrors reader.axis_matrix. */
function meshExtent(bbox: MeshBbox, forward: string, up: string) {
  const f = AXIS_VECTORS[forward] ?? AXIS_VECTORS.Y
  const u = AXIS_VECTORS[up] ?? AXIS_VECTORS.Z
  if (Math.abs(f[0] * u[0] + f[1] * u[1] + f[2] * u[2]) > 0.5) return null
  const east = [
    f[1] * u[2] - f[2] * u[1],
    f[2] * u[0] - f[0] * u[2],
    f[0] * u[1] - f[1] * u[0],
  ]
  const rows = [east, f, u]
  const lo = [
    Number.POSITIVE_INFINITY,
    Number.POSITIVE_INFINITY,
    Number.POSITIVE_INFINITY,
  ]
  const hi = [
    Number.NEGATIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
  ]
  for (const sx of [-1, 1])
    for (const sy of [-1, 1])
      for (const sz of [-1, 1]) {
        const p = [
          bbox.offset[0] + (sx * bbox.size[0]) / 2,
          bbox.offset[1] + (sy * bbox.size[1]) / 2,
          bbox.offset[2] + (sz * bbox.size[2]) / 2,
        ]
        rows.forEach((r, i) => {
          const v = r[0] * p[0] + r[1] * p[1] + r[2] * p[2]
          lo[i] = Math.min(lo[i], v)
          hi[i] = Math.max(hi[i], v)
        })
      }
  return { lo, hi }
}

const num = (v: unknown) =>
  v === "" || v === null || v === undefined ? Number.NaN : Number(v)

export default function PreviewMap({
  kind,
  values,
  features,
  bbox,
  status,
  onPick,
}: PreviewMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [viewer, setViewer] = useState<Cesium.Viewer | null>(null)
  const pickRef = useRef(onPick)
  pickRef.current = onPick
  const featureEntities = useRef<Cesium.Entity[][]>([])
  const meshEntities = useRef<{
    box: Cesium.Entity
    origin: Cesium.Entity
  } | null>(null)
  const zoomedFor = useRef<unknown>(null)
  const [models, setModels] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!containerRef.current) return
    const { viewer } = createViewer(containerRef.current)
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction(
      (e: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        if (!pickRef.current) return
        const cartesian = viewer.camera.pickEllipsoid(
          e.position,
          viewer.scene.globe.ellipsoid,
        )
        if (!cartesian) return
        const c = Cesium.Cartographic.fromCartesian(cartesian)
        pickRef.current(
          Number(Cesium.Math.toDegrees(c.latitude).toFixed(7)),
          Number(Cesium.Math.toDegrees(c.longitude).toFixed(7)),
        )
      },
      Cesium.ScreenSpaceEventType.LEFT_CLICK,
    )
    setViewer(viewer)
    return () => {
      handler.destroy()
      viewer.destroy()
      setViewer(null)
      featureEntities.current = []
      meshEntities.current = null
    }
  }, [])

  function zoom() {
    if (!viewer || viewer.entities.values.length === 0) return
    viewer.zoomTo(
      viewer.entities,
      new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-40), 0),
    )
  }

  useEffect(() => {
    if (!viewer || kind === "Mesh") return
    viewer.entities.removeAll()
    featureEntities.current = (features ?? []).map((feature) => {
      if (kind === "Polygon") {
        return polygonParts(feature).map((rings) =>
          viewer.entities.add({
            polygon: {
              hierarchy: new Cesium.PolygonHierarchy(
                ringPositions(rings[0]),
                rings
                  .slice(1)
                  .map((h) => new Cesium.PolygonHierarchy(ringPositions(h))),
              ),
              height: 0,
              material: FILL,
              outline: true,
              outlineColor: EDGE,
            },
          }),
        )
      }
      return feature.geometry?.type === "Point"
        ? [viewer.entities.add({ point: { pixelSize: 5 } })]
        : []
    })
    viewer.scene.requestRender()
  }, [features, kind, viewer])

  // as in the worker: absolute heights, default the footprint mean Z
  const lower = values.lower_limit_height
  const upper = values.upper_limit_height
  useEffect(() => {
    if (
      !viewer ||
      kind !== "Polygon" ||
      isInvalidExpression(lower) ||
      isInvalidExpression(upper)
    )
      return
    ;(features ?? []).forEach((feature, i) => {
      const lo = evalOr("number", lower, feature, null)
      const hi = evalOr("number", upper, feature, null)
      polygonParts(feature).forEach((rings, j) => {
        const entity = featureEntities.current[i]?.[j]
        if (!entity?.polygon) return
        const outer = rings[0]
        const ground =
          outer.reduce((s, c) => s + (c[2] ?? 0), 0) / Math.max(outer.length, 1)
        let zLow = (lo ?? ground) as number
        let zHigh = (hi ?? ground) as number
        if (zLow > zHigh) [zLow, zHigh] = [zHigh, zLow]
        entity.polygon.height = new Cesium.ConstantProperty(zLow)
        entity.polygon.extrudedHeight =
          lo === null && hi === null
            ? undefined
            : new Cesium.ConstantProperty(zHigh)
      })
    })
    viewer.scene.requestRender()
  }, [features, kind, lower, upper, viewer])

  const instanceExprs = [
    values.model,
    values.scale,
    values.rotation,
    values.translate_z,
  ]
  const instanceValid = !instanceExprs.some(isInvalidExpression)
  const modelKeys = useMemo(() => {
    if (kind !== "Instance" || !instanceValid) return []
    const keys = (features ?? []).map(
      (f) =>
        `${values.models_prefix || ""}${evalOr(
          "string",
          values.model,
          f,
          "model.glb",
        )}`,
    )
    return keys
  }, [kind, features, values.model, values.models_prefix, instanceValid])

  useEffect(() => {
    const unknown = [...new Set(modelKeys)]
      .filter((k) => !(k in models))
      .slice(0, 20)
    if (!unknown.length) return
    let cancelled = false
    Promise.all(
      unknown.map((key) =>
        fetch(modelUrl(key))
          .then((r) => {
            r.body?.cancel()
            return [key, r.ok] as const
          })
          .catch(() => [key, false] as const),
      ),
    ).then((pairs) => {
      if (!cancelled) setModels((m) => ({ ...m, ...Object.fromEntries(pairs) }))
    })
    return () => {
      cancelled = true
    }
  }, [modelKeys, models])

  useEffect(() => {
    if (!viewer || kind !== "Instance" || !instanceValid) return
    ;(features ?? []).forEach((feature, i) => {
      const entity = featureEntities.current[i]?.[0]
      const coords = feature.geometry?.coordinates
      if (!entity || !coords) return
      const scale = Number(evalOr("number", values.scale, feature, 1))
      const rotation = Number(evalOr("number", values.rotation, feature, 0))
      const tz = Number(evalOr("number", values.translate_z, feature, 0))
      const position = Cesium.Cartesian3.fromDegrees(
        coords[0],
        coords[1],
        (coords[2] ?? 0) + tz,
      )
      entity.position = new Cesium.ConstantPositionProperty(position)
      // worker rotation is counter-clockwise, Cesium heading clockwise
      entity.orientation = new Cesium.ConstantProperty(
        Cesium.Transforms.headingPitchRollQuaternion(
          position,
          new Cesium.HeadingPitchRoll(Cesium.Math.toRadians(-rotation), 0, 0),
        ),
      )
      const key = modelKeys[i]
      const found = models[key]
      entity.point = new Cesium.PointGraphics({
        pixelSize: 5,
        color: found === false ? MISSING : Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 1,
      })
      if (found) {
        const uri = modelUrl(key)
        const current = entity.model?.uri?.getValue(Cesium.JulianDate.now())
        if (!entity.model || current !== uri) {
          entity.model = new Cesium.ModelGraphics({ uri, scale })
        } else {
          entity.model.scale = new Cesium.ConstantProperty(scale)
        }
      } else {
        entity.model = undefined
      }
    })
    viewer.scene.requestRender()
  }, [
    features,
    kind,
    values.scale,
    values.rotation,
    values.translate_z,
    modelKeys,
    models,
    instanceValid,
    viewer,
  ])

  const lat = num(values.latitude)
  const lon = num(values.longitude)
  const alt = Number.isNaN(num(values.altitude)) ? 0 : num(values.altitude)
  const extent = useMemo(
    () =>
      bbox
        ? meshExtent(bbox, values.forward_axis || "Y", values.up_axis || "Z")
        : null,
    [bbox, values.forward_axis, values.up_axis],
  )
  const placed =
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lon) <= 180
  useEffect(() => {
    if (!viewer || kind !== "Mesh") return
    if (!placed) {
      viewer.entities.removeAll()
      meshEntities.current = null
      viewer.scene.requestRender()
      return
    }
    if (!meshEntities.current) {
      viewer.entities.removeAll()
      meshEntities.current = {
        box: viewer.entities.add({
          polygon: {
            hierarchy: [],
            height: 0,
            material: MESH_FILL,
            outline: true,
            outlineColor: MESH_EDGE,
          },
        }),
        origin: viewer.entities.add({
          point: {
            pixelSize: 9,
            color: MESH_EDGE,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        }),
      }
    }
    const { box, origin } = meshEntities.current
    origin.position = new Cesium.ConstantPositionProperty(
      Cesium.Cartesian3.fromDegrees(lon, lat, alt),
    )
    box.show = !!extent
    if (extent && box.polygon) {
      const dLon = (e: number) =>
        lon + e / (METERS_PER_DEGREE * Math.cos(Cesium.Math.toRadians(lat)))
      const dLat = (n: number) => lat + n / METERS_PER_DEGREE
      const [e0, n0, u0] = extent.lo
      const [e1, n1, u1] = extent.hi
      box.polygon.hierarchy = new Cesium.ConstantProperty(
        new Cesium.PolygonHierarchy(
          Cesium.Cartesian3.fromDegreesArray([
            dLon(e0),
            dLat(n0),
            dLon(e1),
            dLat(n0),
            dLon(e1),
            dLat(n1),
            dLon(e0),
            dLat(n1),
          ]),
        ),
      )
      box.polygon.height = new Cesium.ConstantProperty(alt + u0)
      box.polygon.extrudedHeight = new Cesium.ConstantProperty(alt + u1)
    }
    viewer.scene.requestRender()
  }, [kind, placed, lat, lon, alt, extent, viewer])

  useEffect(() => {
    if (!viewer) return
    const target = kind === "Mesh" ? (placed && extent ? bbox : null) : features
    if (!target || zoomedFor.current === target) return
    zoomedFor.current = target
    setTimeout(zoom, 0)
  }, [viewer, kind, features, bbox, placed, extent])

  const missing = Object.entries(models)
    .filter(([k, ok]) => !ok && modelKeys.includes(k))
    .map(([k]) => k)
  const notes: string[] = []
  if (status) notes.push(status)
  if (kind === "Mesh") {
    notes.push(
      placed
        ? "Click the map to move the mesh origin"
        : "Click the map to place the mesh origin",
    )
    if (extent === null && bbox) notes.push("Forward and up axis must differ")
  } else if (features && !status) {
    notes.push(`Preview of ${features.length} neighbouring features`)
  }
  if (missing.length) {
    notes.push(
      `Model not found: ${missing.slice(0, 3).join(", ")}${
        missing.length > 3 ? ` +${missing.length - 3} more` : ""
      }`,
    )
  }

  return (
    <Box
      pos="relative"
      w="100%"
      h="100%"
      borderRadius="md"
      overflow="hidden"
      bg="gray.900"
    >
      <Box
        ref={containerRef}
        w="100%"
        h="100%"
        cursor={kind === "Mesh" ? "crosshair" : undefined}
      />
      <VStack
        pos="absolute"
        top={2}
        left={2}
        right={12}
        align="start"
        spacing={1}
        pointerEvents="none"
      >
        {notes.map((n) => (
          <Text
            key={n}
            fontSize="xs"
            color="white"
            bg="blackAlpha.700"
            px={2}
            py={0.5}
            borderRadius="sm"
          >
            {n}
          </Text>
        ))}
      </VStack>
      <Tooltip label="Zoom to preview">
        <IconButton
          aria-label="Zoom to preview"
          icon={<FiCrosshair />}
          size="sm"
          pos="absolute"
          top={2}
          right={2}
          onClick={zoom}
        />
      </Tooltip>
    </Box>
  )
}
