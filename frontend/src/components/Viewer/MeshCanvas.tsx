import {
  Badge,
  Box,
  Button,
  ButtonGroup,
  Checkbox,
  Container,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Text,
} from "@chakra-ui/react"
import { useMemo, useRef, useState } from "react"
import { FiDownload } from "react-icons/fi"
import type { PipelinePublicExtended } from "../../client"
import MeshMapPicker from "./MeshMapPicker"
import { getPublicBasePath } from "../../utils"
import { parseMeshSize } from "../../utils/meshFootprint"
import {
  celeryTaskStatusColor,
  celeryTaskStatusLabel,
  isCeleryTaskInProgress,
} from "../../utils/celeryStatus"

interface MeshCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: Record<string, unknown>) => void
  onUpdate: (payload: Record<string, unknown>) => void
  onCancel: () => void
  assetId: string
}

function MeshCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
}: MeshCanvasProps) {
  const meshSize = useMemo(() => {
    const candidates = [
      pipeline.asset?.upload_result?.size,
      pipeline.data?.size,
      pipeline.task_result?.size,
    ]
    for (const candidate of candidates) {
      const parsed = parseMeshSize(candidate)
      if (parsed) {
        return parsed
      }
    }
    return null
  }, [
    pipeline.asset?.upload_result?.size,
    pipeline.data?.size,
    pipeline.task_result?.size,
  ])

  const [data, setData] = useState({
    latitude: 0,
    longitude: 0,
    altitude: 0,
    depth: 4,
    tile_faces_target: 10000,
    texture_image_size: 512,
    max_geometric_error: 256,
    decimate_last_depth_level: false,
    ...pipeline.data,
  })
  const [zoomToLocationKey, setZoomToLocationKey] = useState(0)
  const skipNextLocationBlurZoomRef = useRef(false)

  const tileset: string | undefined = pipeline?.task_result?.tileset as
    | string
    | undefined
  const download = `${pipeline?.task_result?.download ?? ""}`
  const isRunning = isCeleryTaskInProgress(pipeline.task_status)

  function handleOnChange(key: string, value: number | boolean) {
    setData((prev) => ({ ...prev, [key]: value }))
  }

  function handleLocationChange(latitude: number, longitude: number) {
    setData((prev) => ({ ...prev, latitude, longitude }))
  }

  function requestLocationZoom() {
    setZoomToLocationKey((key) => key + 1)
  }

  function handleLocationFieldKeyDown(
    event: React.KeyboardEvent<HTMLInputElement>,
  ) {
    if (event.key !== "Enter") {
      return
    }
    skipNextLocationBlurZoomRef.current = true
    event.currentTarget.blur()
    requestLocationZoom()
  }

  function handleLocationFieldBlur(
    event: React.FocusEvent<HTMLInputElement>,
  ) {
    if (skipNextLocationBlurZoomRef.current) {
      skipNextLocationBlurZoomRef.current = false
      return
    }
    const next = event.relatedTarget as HTMLElement | null
    if (next?.id === "latitude" || next?.id === "longitude") {
      return
    }
    requestLocationZoom()
  }

  return (
    <Flex w="100%" h="100%">
      <Box w="300px" flexShrink={0} overflowY="auto">
        <Container>
          <Heading
            size="md"
            mb={8}
            textAlign={{ base: "center", md: "left" }}
            pt={12}
          >
            {pipeline.title}
          </Heading>
          <Flex
            mt={2}
            mb={2}
            justifyContent="space-between"
            alignItems="center"
          >
            <Flex gap={2}>
              <Badge colorScheme={celeryTaskStatusColor(pipeline.task_status)}>
                {celeryTaskStatusLabel(pipeline.task_status)}
              </Badge>
              {pipeline.task_result && (
                <a href={download} download={`${pipeline.title}.zip`}>
                  <FiDownload fontSize="16px" />
                </a>
              )}
            </Flex>

            <ButtonGroup size="xs">
              {!isRunning && (
                <Button
                  colorScheme="yellow"
                  variant="outline"
                  onClick={() => onUpdate(data)}
                >
                  Save
                </Button>
              )}
              {isRunning && (
                <Button
                  colorScheme="red"
                  variant="outline"
                  onClick={() => onCancel()}
                >
                  Cancel
                </Button>
              )}
              <Button
                isLoading={isRunning}
                variant="outline"
                onClick={() => onRun(data)}
              >
                Run
              </Button>
            </ButtonGroup>
          </Flex>
          {tileset && (
            <Flex mt={2} mb={2}>
              <Text fontSize="xs">
                <a
                  target="_blank"
                  href={`${getPublicBasePath()}preview.html?${tileset}`}
                  rel="noreferrer"
                >
                  {tileset}
                </a>
              </Text>
            </Flex>
          )}
          <Divider my={4} />
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="latitude">
              Latitude
            </FormLabel>
            <Input
              id="latitude"
              size="xs"
              type="number"
              step="any"
              value={data.latitude}
              onChange={(e) =>
                handleOnChange("latitude", Number(e.target.value))
              }
              onKeyDown={handleLocationFieldKeyDown}
              onBlur={handleLocationFieldBlur}
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="longitude">
              Longitude
            </FormLabel>
            <Input
              id="longitude"
              size="xs"
              type="number"
              step="any"
              value={data.longitude}
              onChange={(e) =>
                handleOnChange("longitude", Number(e.target.value))
              }
              onKeyDown={handleLocationFieldKeyDown}
              onBlur={handleLocationFieldBlur}
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="altitude">
              Altitude (m)
            </FormLabel>
            <Input
              id="altitude"
              size="xs"
              type="number"
              step="any"
              value={data.altitude}
              onChange={(e) =>
                handleOnChange("altitude", Number(e.target.value))
              }
            />
          </FormControl>
          {!meshSize && (
            <Text fontSize="xs" color="gray.500" mb={4}>
              Mesh dimensions are not available yet. Re-upload or re-inspect the
              asset to show the footprint on the map.
            </Text>
          )}
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="depth">
              Depth
            </FormLabel>
            <Input
              id="depth"
              size="xs"
              type="number"
              value={data.depth}
              onChange={(e) => handleOnChange("depth", Number(e.target.value))}
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="tile_faces_target">
              Tile faces target
            </FormLabel>
            <Input
              id="tile_faces_target"
              size="xs"
              type="number"
              value={data.tile_faces_target}
              onChange={(e) =>
                handleOnChange("tile_faces_target", Number(e.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="texture_image_size">
              Texture image size
            </FormLabel>
            <Input
              id="texture_image_size"
              size="xs"
              type="number"
              value={data.texture_image_size}
              onChange={(e) =>
                handleOnChange("texture_image_size", Number(e.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="max_geometric_error">
              Max geometric error
            </FormLabel>
            <Input
              id="max_geometric_error"
              size="xs"
              type="number"
              step="any"
              value={data.max_geometric_error}
              onChange={(e) =>
                handleOnChange("max_geometric_error", Number(e.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={4}>
            <Checkbox
              id="decimate_last_depth_level"
              size="sm"
              isChecked={!!data.decimate_last_depth_level}
              onChange={(e) =>
                handleOnChange("decimate_last_depth_level", e.target.checked)
              }
            >
              Decimate last depth level
            </Checkbox>
          </FormControl>
        </Container>
      </Box>
      <Box flex="1" minH="100%" pos="relative">
        <MeshMapPicker
          latitude={data.latitude}
          longitude={data.longitude}
          onLocationChange={handleLocationChange}
          meshSizeMeters={meshSize ?? undefined}
          zoomToLocationKey={zoomToLocationKey}
        />
      </Box>
    </Flex>
  )
}

export default MeshCanvas
