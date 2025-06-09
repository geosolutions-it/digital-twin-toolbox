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
  Spinner,
  Select,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import React from "react"
import { FiDownload } from "react-icons/fi"
import { AssetsService } from "../../client"
import type { PipelinePublicExtended } from "../../client"
import ThreeCanvas from "./ThreeCanvas"
import { getPublicBasePath } from '../../utils'

interface PhotogrammetryCanvasCanvasProps {
  pipeline: PipelinePublicExtended
  onRun: (payload: any) => any
  onUpdate: (payload: any) => any
  onCancel: () => any
  assetId: string
}

function PhotogrammetryCanvas({
  pipeline,
  onRun,
  onUpdate,
  onCancel,
  assetId,
}: PhotogrammetryCanvasCanvasProps) {
//   const { data: text, isPending } = useQuery({
//     queryFn: () => AssetsService.readAssetSample({ id: assetId }),
//     queryKey: ["pipeline-asset-sample", assetId],
//   })

  const updateScene = (group: any, material: any) => {
    if (!group) {
      return null
    }
    for (let i = 0; i < group.children.length; i++) {
      const mesh: any = group.children[i]
      mesh.geometry.dispose()
    }
    group.children.forEach((child: any) => group.remove(child))
    group.children = []
  }

  const group = React.useRef()
  const material = React.useRef()

  const [data, setData] = React.useState({
    stage: 'all',
    image_process_size: 2048,
    depthmap_process_size: 2048,
    ...pipeline.data,
  })

  function handleOnChange(key: string, value: any) {
    const newData = { ...data, [key]: value }
    setData(newData)
  }

  function handleInitializeScene(config: any) {
    group.current = config.group
    material.current = config.pointMaterial
    updateScene(group.current, material.current)
  }

  // @ts-ignore collection
  const tileset: any = pipeline?.task_result?.tileset
  const download: string = `${pipeline?.task_result?.download}`

//   if (isPending) {
//     return (
//       <Container maxW="full" pt={12}>
//         {" "}
//         <Spinner size="xl" />
//       </Container>
//     )
//   }

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
            <FormLabel fontSize="xs" htmlFor="stage">
              Image process size
            </FormLabel>
            <Select
              id="stage"
              size="xs"
              value={data?.stage}
              onChange={(event: any) =>
                handleOnChange("stage", event?.target?.value)
              }
            >
              <option value={'all'}>
                All
              </option>
              <option value={'images_to_point_cloud'}>
                Images to point cloud
              </option>
              <option value={'point_cloud_to_mesh'}>
                Point cloud to mesh
              </option>
              <option value={'mesh_to_3dtile'}>
                Mesh to 3D Tile
              </option>
            </Select>
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="image_process_size">
              Image process size
            </FormLabel>
            <Input
              id="image_process_size"
              size="xs"
              type="number"
              defaultValue={data?.image_process_size}
              onChange={(event) =>
                handleOnChange("image_process_size", event.target.value)
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2}>
            <FormLabel fontSize="xs" htmlFor="depthmap_process_size">
              Depth map process size
            </FormLabel>
            <Input
              id="depthmap_process_size"
              size="xs"
              type="number"
              defaultValue={data?.depthmap_process_size}
              onChange={(event) =>
                handleOnChange("depthmap_process_size", event.target.value)
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
export default PhotogrammetryCanvas
