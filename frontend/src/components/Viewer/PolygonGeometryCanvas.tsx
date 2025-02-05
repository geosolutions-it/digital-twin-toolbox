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
  Spinner,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import turfBbox from "@turf/bbox"
import React from "react"
import { FiDownload } from "react-icons/fi"
import { BufferAttribute, BufferGeometry, Mesh } from "three"
import { AssetsService } from "../../client"
import type { PipelinePublicExtended } from "../../client"
import { OpenAPI } from "../../client/core/OpenAPI"
import {
  convertToCartesian,
  translateAndRotate,
} from "../../utils/cartesian.js"
import { parseExpression } from "../../utils/expression"
import { collectionToPolyhedralSurfaceZ } from "../../utils/polyhedron"
import InputExpression from "./InputExpression.js"
import ThreeCanvas from "./ThreeCanvas"

interface PolygonGeometryCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: any) => any
  onUpdate: (payload: any) => any
  onCancel: () => any
  assetId: string
}

function PolygonGeometryCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
  assetId,
}: PolygonGeometryCanvasProps) {
  const { data: collection, isPending } = useQuery({
    queryFn: () => AssetsService.readAssetSample({ id: assetId }),
    queryKey: ["pipeline-asset-sample", assetId],
  })

  const updateScene = (group: any, material: any, config: any) => {
    if (!collection || !group) {
      return null
    }
    for (let i = 0; i < group.children.length; i++) {
      const mesh: any = group.children[i]
      mesh.geometry.dispose()
    }
    group.children.forEach((child: any) => group.remove(child))
    //@ts-ignore
    const [minx, miny, maxx, maxy] = turfBbox(collection)
    const center = [minx + (maxx - minx) / 2, miny + (maxy - miny) / 2, 0]
    const cartesian = convertToCartesian(center)
    const polyhedralSurfaceCollection = collectionToPolyhedralSurfaceZ(
      collection,
      {
        filter: config?.filter ? config.filter : (feature: any) => feature,
        computeOptions: (feature: any) => {
          return {
            lowerLimit: parseExpression(
              "number",
              config?.lower_limit_height,
              feature,
            ),
            upperLimit: parseExpression(
              "number",
              config?.upper_limit_height,
              feature,
            ),
            translateZ: parseExpression("number", config?.translate_z, feature),
            removeBottomSurface: !!config?.remove_bottom_surface,
          }
        },
      },
    )

    for (let i = 0; i < polyhedralSurfaceCollection.features.length; i++) {
      const feature: any = polyhedralSurfaceCollection.features[i]
      const coordinates = feature.geometry.coordinates
      const vertices = new Float32Array(
        coordinates
          .reduce((acc: any, triangle: number[][]) => {
            const [a, b, c] = triangle
            return acc.concat(
              [a, b, c].map((vertex) => translateAndRotate(vertex, cartesian)),
            )
          }, [])
          .flat(),
      )
      const geometry = new BufferGeometry()
      geometry.setAttribute("position", new BufferAttribute(vertices, 3))
      geometry.computeVertexNormals()
      const mesh = new Mesh(geometry, material)
      group.add(mesh)
    }
  }

  const group = React.useRef()
  const material = React.useRef()
  const timeout = React.useRef(0)

  const [data, setData] = React.useState({
    lower_limit_height: undefined,
    upper_limit_height: undefined,
    translate_z: 0,
    max_features_per_tile: 100,
    double_sided: false,
    remove_bottom_surface: true,
    min_geometric_error: 0,
    max_geometric_error: 250,
    ...pipeline.data,
  })

  function handleOnChange(key: string, value: any) {
    const newData = { ...data, [key]: value }
    setData(newData)
    if (timeout.current) {
      window.clearTimeout(timeout.current)
    }
    timeout.current = window.setTimeout(() => {
      updateScene(group.current, material.current, newData)
      timeout.current = 0
    }, 300)
  }

  function handleInitializeScene(config: any) {
    group.current = config.group
    material.current = config.material
    updateScene(group.current, material.current, data)
  }

  // @ts-ignore collection
  const properties = collection?.features?.[0]?.properties
  const tileset: any = pipeline?.task_result?.tileset
  const download: string = `${OpenAPI.BASE}${pipeline?.task_result?.download}`

  if (isPending) {
    return (
      <Container maxW="full" pt={12}>
        {" "}
        <Spinner size="xl" />
      </Container>
    )
  }

  return (
    <>
      <Box w="300px">
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
                  pipeline.task_status === "PENDING"
                    ? "yellow"
                    : pipeline.task_status === "SUCCESS"
                      ? "green"
                      : "red"
                }
              >
                {pipeline.task_status}
              </Badge>
              {pipeline.task_result && (
                <a href={download} download={`${pipeline.title}.zip`}>
                  <FiDownload fontSize="16px" />
                </a>
              )}
            </Flex>
            <ButtonGroup size="xs">
              {pipeline.task_status !== "PENDING" && (
                <Button
                  colorScheme={"yellow"}
                  variant="outline"
                  onClick={() => onUpdate(data)}
                >
                  Save
                </Button>
              )}
              {pipeline.task_status === "PENDING" && (
                <Button
                  colorScheme="red"
                  variant="outline"
                  onClick={() => onCancel()}
                >
                  Cancel
                </Button>
              )}
              <Button
                isLoading={pipeline.task_status === "PENDING"}
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
                {
                  <a
                    target="_blank"
                    href={`/preview.html?${OpenAPI.BASE}${tileset}`}
                    rel="noreferrer"
                  >
                    {tileset}
                  </a>
                }
              </Text>
            </Flex>
          )}
          <Divider />
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="lower_limit_height">
              Lower limit height
            </FormLabel>
            <InputExpression
              id="lower_limit_height"
              type="number"
              value={data?.lower_limit_height}
              onChange={handleOnChange.bind(null, "lower_limit_height")}
              properties={properties}
            />
          </FormControl>
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="upper_limit_height">
              Upper limit height
            </FormLabel>
            <InputExpression
              id="upper_limit_height"
              type="number"
              value={data?.upper_limit_height}
              onChange={handleOnChange.bind(null, "upper_limit_height")}
              properties={properties}
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="translate_z">
              Translate z
            </FormLabel>
            <InputExpression
              id="translate_z"
              type="number"
              value={data?.translate_z}
              onChange={handleOnChange.bind(null, "translate_z")}
              properties={properties}
            />
          </FormControl>
          <Divider />
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="max_features_per_tile">
              Maximum features per tile
            </FormLabel>
            <Input
              id="max_features_per_tile"
              size="xs"
              type="number"
              value={data?.max_features_per_tile}
              onChange={(event) =>
                handleOnChange("max_features_per_tile", event.target.value)
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="max_geometric_error">
              Maximum geometric error
            </FormLabel>
            <Input
              id="max_geometric_error"
              size="xs"
              type="number"
              value={data?.max_geometric_error}
              onChange={(event) =>
                handleOnChange("max_geometric_error", event.target.value)
              }
            />
          </FormControl>
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="min_geometric_error">
              Minimum geometric error
            </FormLabel>
            <Input
              id="min_geometric_error"
              size="xs"
              type="number"
              value={data?.min_geometric_error}
              onChange={(event) =>
                handleOnChange("min_geometric_error", event.target.value)
              }
            />
          </FormControl>
          <Flex mt={2}>
            <Checkbox
              id="remove_bottom_surface"
              size="sm"
              isChecked={data?.remove_bottom_surface}
              onChange={(event) =>
                handleOnChange("remove_bottom_surface", event.target.checked)
              }
            >
              Remove bottom surface
            </Checkbox>
          </Flex>
          <Flex mt={2} mb={2}>
            <Checkbox
              id="double_sided"
              size="sm"
              isChecked={data?.double_sided}
              onChange={(event) =>
                handleOnChange("double_sided", event.target.checked)
              }
            >
              Double sided
            </Checkbox>
          </Flex>

          <Divider />
        </Container>
      </Box>
      <Divider orientation="vertical" />
      <Box flex="1" pos="relative">
        <ThreeCanvas onMount={handleInitializeScene} />
      </Box>
    </>
  )
}

export default PolygonGeometryCanvas
