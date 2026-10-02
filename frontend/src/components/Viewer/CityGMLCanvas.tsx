import {
  Badge,
  Box,
  Button,
  ButtonGroup,
  Container,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Text,
} from "@chakra-ui/react"
import { useMemo, useState } from "react"
import { FiDownload } from "react-icons/fi"
import type { PipelinePublicExtended } from "../../client"
import { getPublicBasePath } from "../../utils"
import { parseWgs84Bbox } from "../../utils/mapBBox"
import MapBBoxViewer from "./MapBBoxViewer"

interface CityGMLCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: Record<string, unknown>) => void
  onUpdate: (payload: Record<string, unknown>) => void
  onCancel: () => void
  assetId: string
}

function CityGMLCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
}: CityGMLCanvasProps) {
  const detectedCrs = pipeline.asset?.upload_result?.epsg
  const previewBbox = useMemo(
    () => parseWgs84Bbox(pipeline.asset?.upload_result?.bbox),
    [pipeline.asset?.upload_result?.bbox],
  )

  const initialCrs =
    Number(pipeline.data?.crs ?? detectedCrs) || undefined

  const [data, setData] = useState({
    feature_count_target: 2000,
    max_workers: 4,
    ...pipeline.data,
    crs: initialCrs,
  })

  const tileset: string | undefined = pipeline?.task_result?.tileset as
    | string
    | undefined
  const download = `${pipeline?.task_result?.download ?? ""}`
  const isRunning =
    pipeline.task_status === "PENDING" ||
    pipeline.task_status === "STARTED"
  const canRun = Boolean(data.crs && Number(data.crs) > 0)

  function handleOnChange(key: string, value: number) {
    setData((prev) => ({ ...prev, [key]: value }))
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
              <Badge
                colorScheme={
                  isRunning
                    ? "yellow"
                    : pipeline.task_status === "SUCCESS"
                      ? "green"
                      : "red"
                }
              >
                {isRunning ? "RUNNING" : pipeline.task_status}
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
                isDisabled={!canRun}
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
            <FormLabel fontSize="xs" htmlFor="crs">
              CRS (EPSG)
            </FormLabel>
            <Input
              id="crs"
              size="xs"
              type="number"
              value={data.crs ?? ""}
              onChange={(e) =>
                handleOnChange("crs", Number(e.target.value) || 0)
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="feature_count_target">
              Feature count target
            </FormLabel>
            <Input
              id="feature_count_target"
              size="xs"
              type="number"
              value={data.feature_count_target}
              onChange={(e) =>
                handleOnChange("feature_count_target", Number(e.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={4}>
            <FormLabel fontSize="xs" htmlFor="max_workers">
              Max workers
            </FormLabel>
            <Input
              id="max_workers"
              size="xs"
              type="number"
              value={data.max_workers}
              onChange={(e) =>
                handleOnChange("max_workers", Number(e.target.value))
              }
            />
          </FormControl>
          {!previewBbox && (
            <Text fontSize="xs" color="gray.500" mb={4}>
              Bounding box preview is not available yet. Re-upload or
              re-inspect the asset to verify the dataset location on the map.
            </Text>
          )}
        </Container>
      </Box>
      <Box flex="1" minH="100%" pos="relative">
        <MapBBoxViewer bbox={previewBbox} />
      </Box>
    </Flex>
  )
}

export default CityGMLCanvas
