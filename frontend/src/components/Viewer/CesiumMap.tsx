import {
  Badge,
  Box,
  Checkbox,
  Divider,
  Flex,
  Heading,
  IconButton,
  Radio,
  RadioGroup,
  Slider,
  SliderFilledTrack,
  SliderThumb,
  SliderTrack,
  Stack,
  Text,
  Tooltip,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import * as Cesium from "cesium"
import { useEffect, useMemo, useRef, useState } from "react"
import { FiCrosshair, FiX } from "react-icons/fi"
import { API_BASE, readPipelines } from "../../api"
import "cesium/Source/Widgets/widgets.css"

// Workers, shaders and images are copied to public/cesium by scripts/copy-cesium-assets.mjs.
// Absolute because Cesium resolves this against document.baseURI and routes can be nested.
window.CESIUM_BASE_URL = "/cesium/"

declare global {
  interface Window {
    CESIUM_BASE_URL?: string
  }
}

const WMS_URL = "https://maps1.geosolutionsgroup.com/geoserver/wms"
const OSM_CREDIT = "© OpenStreetMap contributors"

type Layer = {
  id: string
  title: string
  type: string
  url: string
  isTerrain: boolean
  extent?: number[]
}

// Each successful pipeline becomes a layer; terrain is told apart by its layer.json.
function soloLayer(p: any): Layer {
  const tileset = String(p.task_result.tileset)
  const type = p?.source?.pipeline || "PointCloud"
  return {
    id: p.id,
    title: p.title || p.id,
    type,
    url: `${API_BASE}${tileset}`,
    isTerrain: tileset.endsWith("layer.json") || type === "Terrain",
    extent: Array.isArray(p.task_result.extent) ? p.task_result.extent : undefined,
  }
}

// Solo pipelines map one-to-one; a batch collapses to one layer on its combined tileset.
function buildLayers(items: any[]): Layer[] {
  const solo: any[] = []
  const batches = new Map<string, any[]>()
  for (const p of items) {
    if (p?.batch_id) {
      const arr = batches.get(p.batch_id)
      if (arr) arr.push(p)
      else batches.set(p.batch_id, [p])
    } else {
      solo.push(p)
    }
  }

  const layers: Layer[] = []
  for (const p of solo) {
    if (p?.task_status === "SUCCESS" && p?.task_result?.tileset) layers.push(soloLayer(p))
  }
  for (const [bid, group] of batches) {
    const allDone = group.length > 0 && group.every((p) => p?.task_status === "SUCCESS")
    const prefix: string = group[0]?.source?.batch_output_prefix || ""
    const child: string = group.find((p) => p?.task_result?.tileset)?.task_result?.tileset || ""
    if (!allDone || !prefix || !child) continue
    const idx = child.indexOf(prefix)
    if (idx < 0) continue
    const t: string = group[0]?.title || ""
    layers.push({
      id: `batch:${bid}`,
      title: t.includes(" / ") ? t.split(" / ")[0] : `Batch ${bid.slice(0, 8)}`,
      type: group[0]?.source?.pipeline || "PointCloud",
      url: `${API_BASE}${child.slice(0, idx)}${prefix}/tileset.json`,
      isTerrain: false,
    })
  }
  return layers
}

// SSE and debug apply to every tileset, shading and classification only to point clouds.
type PcSettings = {
  attenuation: boolean
  eyeDome: boolean
  classification: boolean
  sse: number
  boundingVolume: boolean
  geometricError: boolean
  statistics: boolean
  memory: boolean
}

const DEFAULT_PC: PcSettings = {
  attenuation: true,
  eyeDome: true,
  classification: false,
  sse: 16,
  boundingVolume: false,
  geometricError: false,
  statistics: false,
  memory: false,
}

// Classification palette mirrors frontend/public/preview.html: ground/wheat, veg greens, buildings red.
function classificationStyle() {
  return new Cesium.Cesium3DTileStyle({
    color: {
      conditions: [
        ["${classification} === 1", "color('#FFDEAD')"],
        ["${classification} === 2", "color('#FFDEAD')"],
        ["${classification} === 3", "color('#63FF7E')"],
        ["${classification} === 4", "color('#63FF7E')"],
        ["${classification} === 5", "color('#22B33A')"],
        ["${classification} === 6", "color('#ff0000')"],
        ["${classification} === 7", "color('#808080')"],
        ["${classification} === 8", "color('#808080')"],
        [true, "color('#808080')"],
      ],
    },
  })
}

function applySettings(ts: Cesium.Cesium3DTileset, s: PcSettings, isPointCloud: boolean) {
  ts.maximumScreenSpaceError = s.sse
  if (isPointCloud) {
    ts.pointCloudShading.attenuation = s.attenuation
    ts.pointCloudShading.maximumAttenuation = 4
    ts.pointCloudShading.eyeDomeLighting = s.eyeDome
    ts.style = s.classification ? classificationStyle() : undefined
  }
  ts.debugShowBoundingVolume = s.boundingVolume
  ts.debugShowGeometricError = s.geometricError
  ts.debugShowRenderingStatistics = s.statistics
  ts.debugShowMemoryUsage = s.memory
}

type Picked = {
  props: [string, unknown][]
  tile: string
  geometricError: number
}

function formatValue(v: unknown) {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3)
  return v == null ? "" : String(v)
}

export default function CesiumMap() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const imageryRef = useRef<Cesium.ImageryLayer | null>(null)
  const tilesetsRef = useRef<Map<string, Cesium.Cesium3DTileset>>(new Map())
  const pendingZoom = useRef<string | null>(null)
  const flewRef = useRef(false)
  // Mirror of pcSettings so the async tileset-load effect reads the latest without re-running.
  const pcRef = useRef<PcSettings>(DEFAULT_PC)

  const { data } = useQuery({
    queryKey: ["pipelines", "map"],
    queryFn: () => readPipelines({ skip: 0, limit: 1000 }),
  })
  const layers = useMemo(() => buildLayers((data as any)?.data || []), [data])
  // memoized so effects don't rerun (and reset terrain) on every render
  const tileLayers = useMemo(() => layers.filter((l) => !l.isTerrain), [layers])
  const terrainLayers = useMemo(() => layers.filter((l) => l.isTerrain), [layers])

  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const [activeTerrain, setActiveTerrain] = useState("")
  const [basemap, setBasemap] = useState(true)
  const [pc, setPc] = useState<PcSettings>(DEFAULT_PC)
  const [debugOpen, setDebugOpen] = useState(false)
  const [picked, setPicked] = useState<Picked | null>(null)

  const hasPointCloud = tileLayers.some((l) => l.type === "PointCloud")
  const setPcField = <K extends keyof PcSettings>(k: K, v: PcSettings[K]) =>
    setPc((s) => ({ ...s, [k]: v }))

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return
    const provider = new Cesium.WebMapServiceImageryProvider({
      url: WMS_URL,
      layers: "osm:osm",
      tileWidth: 512,
      tileHeight: 512,
      credit: new Cesium.Credit(OSM_CREDIT),
    })
    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayer: false,
      baseLayerPicker: false,
      animation: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      navigationInstructionsInitiallyVisible: false,
      skyBox: false,
      scene3DOnly: true,
      requestRenderMode: true,
      maximumRenderTimeChange: Number.POSITIVE_INFINITY,
    })
    viewer.scene.globe.baseColor = new Cesium.Color(0.05, 0.05, 0.05, 1)
    const imagery = new Cesium.ImageryLayer(provider)
    viewer.imageryLayers.add(imagery)
    imageryRef.current = imagery
    viewerRef.current = viewer

    let highlighted: { feature: Cesium.Cesium3DTileFeature; color: Cesium.Color } | null = null
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction((e: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      if (highlighted) {
        try {
          highlighted.feature.color = highlighted.color
        } catch {
          // tile unloaded
        }
        highlighted = null
      }
      const obj = viewer.scene.pick(e.position)
      if (obj instanceof Cesium.Cesium3DTileFeature) {
        highlighted = { feature: obj, color: Cesium.Color.clone(obj.color) }
        obj.color = Cesium.Color.YELLOW
        // content is untyped but public
        const content = (obj as unknown as { content: Cesium.Cesium3DTileContent }).content
        setPicked({
          props: obj.getPropertyIds().map((id) => [id, obj.getProperty(id)] as [string, unknown]),
          tile: content.url.split("/").pop()?.split("?")[0] || "",
          geometricError: content.tile.geometricError,
        })
      } else {
        setPicked(null)
      }
      viewer.scene.requestRender()
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    return () => {
      handler.destroy()
      viewer.destroy()
      viewerRef.current = null
      imageryRef.current = null
      tilesetsRef.current.clear()
      flewRef.current = false
    }
  }, [])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    for (const layer of tileLayers) {
      const on = !!visible[layer.id]
      const existing = tilesetsRef.current.get(layer.id)
      if (on && !existing) {
        Cesium.Cesium3DTileset.fromUrl(layer.url)
          .then((ts) => {
            if (!viewerRef.current) return
            tilesetsRef.current.set(layer.id, ts)
            viewer.scene.primitives.add(ts)
            applySettings(ts, pcRef.current, layer.type === "PointCloud")
            if (pendingZoom.current === layer.id) {
              pendingZoom.current = null
              flewRef.current = true
              viewer.flyTo(ts)
            } else if (!flewRef.current) {
              flewRef.current = true
              viewer.flyTo(ts, { duration: 0 })
            }
            viewer.scene.requestRender()
          })
          .catch(() => {})
      } else if (existing) {
        existing.show = on
        viewer.scene.requestRender()
      }
    }
  }, [visible, tileLayers])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let cancelled = false
    ;(async () => {
      if (!activeTerrain) {
        viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider()
        viewer.scene.globe.depthTestAgainstTerrain = false
      } else {
        const layer = terrainLayers.find((l) => l.id === activeTerrain)
        if (!layer) return
        // fromUrl wants the terrain directory and appends layer.json itself.
        const terrainUrl = layer.url.replace(/\/layer\.json$/, "")
        const tp = await Cesium.CesiumTerrainProvider.fromUrl(terrainUrl, {
          requestVertexNormals: true,
          requestWaterMask: true,
        })
        if (cancelled || !viewerRef.current) return
        viewer.terrainProvider = tp
        viewer.scene.globe.depthTestAgainstTerrain = true
        // Local DEMs are a speck on the globe; fly to the data extent.
        if (layer.extent?.length === 4) {
          const [w, s, e, n] = layer.extent
          viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(w, s, e, n) })
        }
      }
      viewer.scene.requestRender()
    })()
    return () => {
      cancelled = true
    }
  }, [activeTerrain, terrainLayers])

  useEffect(() => {
    const viewer = viewerRef.current
    const imagery = imageryRef.current
    if (!viewer || !imagery) return
    imagery.show = basemap
    viewer.scene.requestRender()
  }, [basemap])

  useEffect(() => {
    pcRef.current = pc
    const viewer = viewerRef.current
    if (!viewer) return
    for (const layer of tileLayers) {
      const ts = tilesetsRef.current.get(layer.id)
      if (ts) applySettings(ts, pc, layer.type === "PointCloud")
    }
    viewer.scene.requestRender()
  }, [pc, tileLayers])

  const zoomTo = (layer: Layer) => {
    const ts = tilesetsRef.current.get(layer.id)
    if (ts) {
      viewerRef.current?.flyTo(ts)
      return
    }
    pendingZoom.current = layer.id
    setVisible((v) => ({ ...v, [layer.id]: true }))
  }

  return (
    <Box pos="relative" w="100%" h="100%">
      <style>{".cesium-credit-logoContainer{display:none!important}"}</style>
      <Box ref={containerRef} pos="absolute" inset={0} />

      <Box
        pos="absolute"
        top={4}
        left={4}
        w="260px"
        maxH="calc(100% - 32px)"
        overflowY="auto"
        overflowX="hidden"
        bg="blackAlpha.700"
        color="white"
        borderRadius="md"
        p={3}
        fontSize="sm"
      >
        <Flex align="center" justify="space-between" mb={2}>
          <Heading size="xs" textTransform="uppercase" letterSpacing="wide">
            Layers
          </Heading>
          <Checkbox isChecked={basemap} onChange={(e) => setBasemap(e.target.checked)} size="sm">
            Basemap
          </Checkbox>
        </Flex>

        <Text fontSize="xs" opacity={0.7} mb={1}>
          3D Tiles
        </Text>
        {tileLayers.length === 0 ? (
          <Text fontSize="xs" opacity={0.5}>
            No tilesets yet.
          </Text>
        ) : (
          <Stack spacing={1}>
            {tileLayers.map((layer) => (
              <Flex key={layer.id} align="center" gap={2} minW={0}>
                <Checkbox
                  isChecked={!!visible[layer.id]}
                  onChange={(e) => setVisible((v) => ({ ...v, [layer.id]: e.target.checked }))}
                  size="sm"
                  flexShrink={0}
                />
                <Text
                  flex={1}
                  minW={0}
                  isTruncated
                  title={layer.title}
                  cursor="pointer"
                  onClick={() => setVisible((v) => ({ ...v, [layer.id]: !v[layer.id] }))}
                >
                  {layer.title}
                </Text>
                <Badge fontSize="0.6rem" colorScheme="teal" flexShrink={0}>
                  {layer.type}
                </Badge>
                <Tooltip label="Zoom to">
                  <IconButton
                    aria-label="Zoom to"
                    icon={<FiCrosshair />}
                    size="xs"
                    variant="ghost"
                    colorScheme="whiteAlpha"
                    flexShrink={0}
                    onClick={() => zoomTo(layer)}
                  />
                </Tooltip>
              </Flex>
            ))}
          </Stack>
        )}

        {tileLayers.length > 0 && (
          <>
            <Divider my={3} borderColor="whiteAlpha.300" />
            <Stack spacing={1}>
              {hasPointCloud && (
                <>
                  <Text fontSize="xs" opacity={0.7} mb={1}>
                    Point clouds
                  </Text>
                  <Checkbox
                    isChecked={pc.attenuation}
                    onChange={(e) => setPcField("attenuation", e.target.checked)}
                    size="sm"
                  >
                    Shading (attenuation)
                  </Checkbox>
                  <Checkbox
                    isChecked={pc.eyeDome}
                    onChange={(e) => setPcField("eyeDome", e.target.checked)}
                    size="sm"
                  >
                    Eye-dome lighting
                  </Checkbox>
                  <Checkbox
                    isChecked={pc.classification}
                    onChange={(e) => setPcField("classification", e.target.checked)}
                    size="sm"
                  >
                    Classification colors
                  </Checkbox>
                </>
              )}

              <Flex align="center" justify="space-between" mt={1}>
                <Text fontSize="xs" opacity={0.8}>
                  Screen-space error
                </Text>
                <Text fontSize="xs" fontFamily="mono">
                  {pc.sse}
                </Text>
              </Flex>
              <Slider
                aria-label="Maximum screen-space error"
                min={1}
                max={32}
                step={1}
                value={pc.sse}
                onChange={(v) => setPcField("sse", v)}
              >
                <SliderTrack bg="whiteAlpha.300">
                  <SliderFilledTrack bg="teal.300" />
                </SliderTrack>
                <SliderThumb boxSize={3} />
              </Slider>
              <Text fontSize="0.65rem" opacity={0.5}>
                Lower = denser (more refinement), higher = sparser.
              </Text>
            </Stack>

            <Flex align="center" justify="space-between" mt={2}>
              <Text fontSize="xs" opacity={0.7}>
                Debug
              </Text>
              <Checkbox
                isChecked={debugOpen}
                onChange={(e) => setDebugOpen(e.target.checked)}
                size="sm"
              />
            </Flex>
            {debugOpen && (
              <Stack spacing={1} mt={1} pl={1}>
                <Checkbox
                  isChecked={pc.statistics}
                  onChange={(e) => setPcField("statistics", e.target.checked)}
                  size="sm"
                >
                  Rendering statistics
                </Checkbox>
                <Checkbox
                  isChecked={pc.memory}
                  onChange={(e) => setPcField("memory", e.target.checked)}
                  size="sm"
                >
                  Memory usage
                </Checkbox>
                <Checkbox
                  isChecked={pc.boundingVolume}
                  onChange={(e) => setPcField("boundingVolume", e.target.checked)}
                  size="sm"
                >
                  Bounding volumes
                </Checkbox>
                <Checkbox
                  isChecked={pc.geometricError}
                  onChange={(e) => setPcField("geometricError", e.target.checked)}
                  size="sm"
                >
                  Geometric error
                </Checkbox>
              </Stack>
            )}
          </>
        )}

        <Divider my={3} borderColor="whiteAlpha.300" />

        <Text fontSize="xs" opacity={0.7} mb={1}>
          Terrain
        </Text>
        <RadioGroup value={activeTerrain} onChange={setActiveTerrain}>
          <Stack spacing={1}>
            <Radio value="" size="sm">
              Ellipsoid (flat)
            </Radio>
            {terrainLayers.map((layer) => (
              <Radio key={layer.id} value={layer.id} size="sm">
                <Text isTruncated maxW="190px" title={layer.title}>
                  {layer.title}
                </Text>
              </Radio>
            ))}
          </Stack>
        </RadioGroup>
      </Box>

      {picked && (
        <Box
          pos="absolute"
          top={4}
          right={4}
          w="300px"
          maxH="calc(100% - 32px)"
          overflowY="auto"
          bg="blackAlpha.700"
          color="white"
          borderRadius="md"
          p={3}
          fontSize="xs"
        >
          <Flex align="center" justify="space-between" mb={1}>
            <Heading size="xs" textTransform="uppercase" letterSpacing="wide">
              Feature
            </Heading>
            <IconButton
              aria-label="Close"
              icon={<FiX />}
              size="xs"
              variant="ghost"
              colorScheme="whiteAlpha"
              onClick={() => setPicked(null)}
            />
          </Flex>
          <Text opacity={0.6} mb={2}>
            tile {picked.tile} · geometric error {picked.geometricError.toFixed(1)} m
          </Text>
          {picked.props.length === 0 ? (
            <Text opacity={0.5}>No properties on this feature.</Text>
          ) : (
            <Stack spacing={0}>
              {picked.props.map(([k, v]) => (
                <Flex key={k} gap={2}>
                  <Text opacity={0.7} flexShrink={0} w="110px" isTruncated title={k}>
                    {k}
                  </Text>
                  <Text fontFamily="mono" wordBreak="break-all">
                    {formatValue(v)}
                  </Text>
                </Flex>
              ))}
            </Stack>
          )}
        </Box>
      )}
    </Box>
  )
}
