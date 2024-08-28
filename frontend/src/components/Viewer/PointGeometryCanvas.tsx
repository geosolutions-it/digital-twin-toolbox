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
  Select,
  Spinner,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import turfBbox from "@turf/bbox"
import React from "react"
import { FiDownload } from "react-icons/fi"
import { InstancedMesh, MathUtils, Object3D } from "three"
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js"
import { AssetsService } from "../../client"
import type { PipelinePublicExtended } from "../../client"
import { OpenAPI } from "../../client/core/OpenAPI"
import { getHeaders } from "../../client/core/request.js"
import {
  convertToCartesian,
  translateAndRotate,
} from "../../utils/cartesian.js"
import { parseExpression } from "../../utils/expression"
import InputExpression from "./InputExpression.js"
import ThreeCanvas from "./ThreeCanvas"

const collectionToPointInstances = (collection: any, options: any) => {
  const computeOptions = options.computeOptions
    ? options.computeOptions
    : () => ({})
  const features = (collection?.features || []).map((feature: any) => {
    const options = computeOptions(feature)
    const coordinates = feature?.geometry?.coordinates || []
    return {
      ...feature,
      properties: {
        scale: options?.scale || 1,
        rotation: options?.rotation || 0,
        model: options?.model || "",
        tags: Object.keys(feature?.properties).map((key) => ({
          [key]: feature.properties[key],
        })),
      },
      geometry: {
        ...feature?.geometry,
        coordinates: [
          coordinates[0],
          coordinates[1],
          (coordinates[2] || 0) + (options?.translateZ || 0),
        ],
      },
    }
  })
  const models = features.reduce((acc: any, feature: any) => {
    if (!acc.includes(feature?.properties?.model)) {
      acc.push(feature?.properties?.model)
    }
    return acc
  }, [])
  return {
    type: "FeatureCollection",
    features,
    models,
  }
}

const dummy = new Object3D()

const loader = new GLTFLoader()

const loadGLB = (model: string) => {
  return getHeaders(OpenAPI, { method: "GET", url: "" }).then((headers) => {
    loader.requestHeader = {
      Authorization: headers.Authorization,
    }
    return new Promise((resolve, reject) => {
      loader.load(
        `${OpenAPI.BASE}/api/v1/assets/files/${model}`,
        (glb) => {
          resolve(glb)
        },
        (xhr) => {
          // progress
          console.log(`${(xhr.loaded / xhr.total) * 100}% glb loaded`)
        },
        (error) => {
          reject(error)
        },
      )
    })
  })
}

interface PointGeometryCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: any) => any
  onUpdate: (payload: any) => any
  onCancel: () => any
  assetId: string
}

function PointGeometryCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
  assetId,
}: PointGeometryCanvasProps) {
  const { data: collection, isPending } = useQuery({
    queryFn: () => AssetsService.readAssetSample({ id: assetId }),
    queryKey: ["pipeline-asset-sample", assetId],
  })

  const { data: models, isPending: isModelPending } = useQuery({
    queryFn: () =>
      AssetsService.readAssets({
        skip: 0,
        limit: 9999,
        extension: ".glb",
      }),
    queryKey: ["assets", "glb"],
  })

  const updateScene = (group: any, material: any, config: any) => {
    if (!collection || !group) {
      return null
    }
    for (let i = 0; i < group.children.length; i++) {
      const mesh: any = group.children[i]
      mesh.geometry.dispose()
    }
    group.remove(...group.children)
    // @ts-ignore collection is currently a simple object in the response
    const [minx, miny, maxx, maxy] = turfBbox(collection)
    const center = [minx + (maxx - minx) / 2, miny + (maxy - miny) / 2, 0]
    const cartesian = convertToCartesian(center)
    const pointInstancesCollection = collectionToPointInstances(collection, {
      computeOptions: (feature: any) => ({
        scale: parseExpression("number", config?.scale, feature),
        rotation: parseExpression("number", config?.rotation, feature),
        translateZ: parseExpression("number", config?.translate_z, feature),
        model: parseExpression("string", config?.model, feature),
      }),
    })
    const models = pointInstancesCollection.models
    Promise.all(
      models.map((model: string) =>
        loadGLB(model).then((glb: any) => {
          glb.scene.traverse((obj: any) => {
            if (obj.isMesh) {
              const features = pointInstancesCollection.features.filter(
                (feature: any) => feature?.properties?.model === model,
              )
              const mesh = new InstancedMesh(
                obj.geometry,
                material,
                features.length,
              )
              features.forEach((feature: any, idx: number) => {
                const coordinates = translateAndRotate(
                  convertToCartesian(feature.geometry.coordinates),
                  cartesian,
                )
                dummy.position.set(
                  coordinates[0],
                  coordinates[1],
                  coordinates[2],
                )
                dummy.rotation.y = -MathUtils.degToRad(
                  feature.properties.rotation,
                )
                dummy.scale.set(
                  feature.properties.scale,
                  feature.properties.scale,
                  feature.properties.scale,
                )
                dummy.updateMatrix()
                mesh.setMatrixAt(idx, dummy.matrix)
              })
              mesh.instanceMatrix.needsUpdate = true
              mesh.computeBoundingSphere()
              // @ts-ignore
              group.add(mesh)
            }
          })
        }),
      ),
    ).catch((error) => {
      console.error(error)
    })
  }
  const group = React.useRef()
  const material = React.useRef()
  const timeout = React.useRef(0)

  const [data, setData] = React.useState({
    model: "model.glb",
    rotation: 0,
    scale: 1,
    translate_z: 0,
    max_features_per_tile: 5000,
    max_geometric_error: 1000,
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

  if (isPending || isModelPending) {
    return (
      <Container maxW="full" pt={12}>
        {" "}
        <Spinner size="xl" />
      </Container>
    )
  }

  if (!models?.data?.length && !isModelPending) {
    return (
      <Container maxW="full" pt={12}>
        Please add a .glb model asset to create a 3D tiles from point instances
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
            <FormLabel fontSize="xs" htmlFor="model">
              Model filename
            </FormLabel>
            <InputExpression
              id="model"
              type="text"
              value={data?.model || ""}
              onChange={handleOnChange.bind(null, "model")}
              properties={properties}
              defaultInput={
                <Select
                  id="model"
                  size="xs"
                  value={data?.model || ""}
                  onChange={(event) =>
                    handleOnChange("model", event.target.value)
                  }
                >
                  <option value={""} />
                  {models?.data.map((model) => {
                    return (
                      <option key={model.id} value={model.filename}>
                        {model.filename}
                      </option>
                    )
                  })}
                </Select>
              }
            />
          </FormControl>
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="rotation">
              Model rotation
            </FormLabel>
            <InputExpression
              id="rotation"
              type="number"
              value={data?.rotation}
              onChange={handleOnChange.bind(null, "rotation")}
              properties={properties}
            />
          </FormControl>
          <FormControl mt={2}>
            <FormLabel fontSize="xs" htmlFor="scale">
              Model scale
            </FormLabel>
            <InputExpression
              id="scale"
              type="number"
              value={data?.scale}
              onChange={handleOnChange.bind(null, "scale")}
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

export default PointGeometryCanvas
