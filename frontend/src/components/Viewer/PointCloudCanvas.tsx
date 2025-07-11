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
  Select,
  Spinner,
  Text
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import React from "react"
import { FiDownload } from "react-icons/fi"
import {
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  Points,
  SRGBColorSpace,
} from "three"
import { AssetsService } from "../../client"
import type { PipelinePublicExtended } from "../../client"
import ThreeCanvas from "./ThreeCanvas"
import { getPublicBasePath } from '../../utils'

interface PolygonGeometryCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: any) => any
  onUpdate: (payload: any) => any
  onCancel: () => any
  assetId: string
}

const mapValue = (
  val: number,
  v1: number,
  v2: number,
  v3: number,
  v4: number,
) => v3 + (v4 - v3) * ((val - v1) / (v2 - v1))

const SelectImage = React.forwardRef((props: any, ref) => {
  const { data: images } = useQuery({
    queryFn: () =>
      AssetsService.readAssets({
        skip: 0,
        limit: 9999,
        extension: ".tif,.tiff",
      }),
    queryKey: ["assets", "tif"],
  })

  if (!images?.data?.length) {
    return null
  }

  return (
    <FormControl mt={2}>
      <FormLabel fontSize="xs" htmlFor="colorization_image">
        Image for colorization
      </FormLabel>
      <Select {...props} ref={ref}>
        <option value={""} />
        {images?.data.map((image) => {
          return (
            <option key={image.id} value={image.filename}>
              {image.filename}
            </option>
          )
        })}
      </Select>
    </FormControl>
  )
})

function PointCloudCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
  assetId,
}: PolygonGeometryCanvasProps) {
  const { data: text, isPending } = useQuery({
    queryFn: () => AssetsService.readAssetSample({ id: assetId }),
    queryKey: ["pipeline-asset-sample", assetId],
  })

  const [pointSize, setPointSize] = React.useState(4)

  const updateScene = (group: any, material: any) => {
    if (!text || !group) {
      return null
    }
    for (let i = 0; i < group.children.length; i++) {
      const mesh: any = group.children[i]
      mesh.geometry.dispose()
    }
    group.children.forEach((child: any) => group.remove(child))
    group.children = []
    // @ts-ignore
    const textArr = text.split(/\n/)
    const [, ...rows] = textArr
      .filter((row: string) => !!row)
      .map((row: string) =>
        row
          .split(",")
          .map((val: string) =>
            val.includes('"') ? val : Number.parseFloat(val),
          ),
      )
    const geometry = new BufferGeometry()
    const positions = []
    const colors = []
    const color = new Color()

    let minZ = Number.POSITIVE_INFINITY
    let maxZ = Number.NEGATIVE_INFINITY

    for (let i = 0; i < rows.length; i++) {
      const z = rows[i][2]
      if (z < minZ) {
        minZ = z
      }
      if (z > maxZ) {
        maxZ = z
      }
    }

    for (let i = 0; i < rows.length; i++) {
      const row = rows[i]
      // positions
      const x = row[0]
      const y = row[2]
      const z = -row[1]
      positions.push(x, y, z)
      // colors

      if (row[3] !== undefined) {
        const vx = row[3] / 255
        const vy = row[4] / 255
        const vz = row[5] / 255
        color.setRGB(vx, vy, vz, SRGBColorSpace)
      } else {
        const value = mapValue(row[2], minZ, maxZ, 0.5, 0.9)
        color.setHSL(value, 0.9, 0.5)
      }
      colors.push(color.r, color.g, color.b)
    }

    geometry.setAttribute("position", new Float32BufferAttribute(positions, 3))
    geometry.setAttribute("color", new Float32BufferAttribute(colors, 3))

    const mesh = new Points(geometry, material)

    group.add(mesh)
  }

  const group = React.useRef()
  const material = React.useRef()

  const [data, setData] = React.useState({
    colorization_image: "",
    to_ellipsoidal_height: false,
    ground_classification: false,
    sample_radius: undefined,
    geometric_error_scale_factor: 1,
    ...pipeline.data,
  })

  function handleOnChange(key: string, value: any) {
    const newData = { ...data, [key]: value }
    setData(newData)
  }

  function handleInitializeScene(config: any) {
    group.current = config.group
    material.current = config.pointMaterial
    // @ts-ignore
    setPointSize(parseFloat(material.current.size))
    updateScene(group.current, material.current)
  }

  // @ts-ignore collection
  const tileset: any = pipeline?.task_result?.tileset
  const download: string = `${pipeline?.task_result?.download}`

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
                    href={`${getPublicBasePath()}preview.html?${tileset}`}
                    rel="noreferrer"
                  >
                    {tileset}
                  </a>
                }
              </Text>
            </Flex>
          )}
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="sample_radius">
              Sample radius
            </FormLabel>
            <Input
              id="sample_radius"
              size="xs"
              type="number"
              defaultValue={data?.sample_radius}
              onChange={(event) =>
                handleOnChange("sample_radius", event.target.value)
              }
            />
          </FormControl>
          <SelectImage
            id="colorization_image"
            size="xs"
            value={data?.colorization_image}
            onChange={(event: any) =>
              handleOnChange("colorization_image", event?.target?.value)
            }
          />
          <Flex mt={2}>
            <Checkbox
              id="to_ellipsoidal_height"
              size="sm"
              isChecked={data?.to_ellipsoidal_height}
              onChange={(event) =>
                handleOnChange("to_ellipsoidal_height", event.target.checked)
              }
            >
              Convert to ellipsoidal height
            </Checkbox>
          </Flex>
          <Flex mt={2} mb={2}>
            <Checkbox
              id="ground_classification"
              size="sm"
              isChecked={data?.ground_classification}
              onChange={(event) =>
                handleOnChange("ground_classification", event.target.checked)
              }
            >
              Ground classification
            </Checkbox>
          </Flex>
          <Divider />
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="geometric_error_scale_factor">
              Geometric error scale factor
            </FormLabel>
            <Input
              id="geometric_error_scale_factor"
              size="xs"
              type="number"
              value={data?.geometric_error_scale_factor}
              onChange={(event) =>
                handleOnChange(
                  "geometric_error_scale_factor",
                  event.target.value,
                )
              }
            />
          </FormControl>
          <Divider />
          <Text fontSize="sm" fontWeight="bold" mb={2} mt={2}>
            Preview
          </Text>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs">
              Point size
            </FormLabel>
            <Input
              id="point_size"
              size="xs"
              type="number"
              value={pointSize}
              onChange={(event) => {
                if (material.current) {
                  const newPointSize = parseFloat(event.target.value)
                  setPointSize(newPointSize)
                  // @ts-ignore
                  material.current.size = newPointSize
                }
              }}
            />
          </FormControl>
        </Container>
      </Box>
      <Divider orientation="vertical" />
      <Box flex="1" pos="relative">
        <ThreeCanvas onMount={handleInitializeScene} />
      </Box>
    </>
  )
}
export default PointCloudCanvas
