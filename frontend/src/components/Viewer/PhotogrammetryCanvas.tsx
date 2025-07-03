import {
  Badge,
  Box,
  Button,
  ButtonGroup,
  Container,
  Divider,
  Flex,
  FormControl,
  Checkbox,
  FormLabel,
  Heading,
  Input,
  Select,
  Text,
  Radio,
  RadioGroup,
  Stack,
  Icon
} from "@chakra-ui/react"
import { useRef, useState, useCallback } from "react"
import * as THREE from "three"
// @ts-ignore
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader"
import { FiDownload, FiX } from "react-icons/fi"
import type { PipelinePublicExtended } from "../../client"
import ThreeCanvas from "./ThreeCanvas"
import { getPublicBasePath } from '../../utils'
import { useQuery } from "@tanstack/react-query"

const VITE_API_URL = import.meta.env.VITE_API_URL

class PhotogrammetryResultService {
  /**
   * Get Photogrammetry Output
   * Get photogrammetry output by pipeline ID.
   * @returns Promise<string> Successful Response
   * @throws Error
   */
  public static async getReconstruction(id: string): Promise<string> {
    try {
      const response = await fetch(`${VITE_API_URL}/api/v1/output/${id}/process/reconstruction.ply`, {
        method: "GET",
      });
      
      if (!response.ok) {
        throw new Error(`Error fetching reconstruction: ${response.status}`);
      }
      
      return await response.text();
    } catch (error) {
      console.error("Failed to get reconstruction:", error);
      throw error;
    }
  }

  public static async getPointcloud(id: string): Promise<string> {
    try {
      const response = await fetch(`${VITE_API_URL}/api/v1/output/${id}/process/undistorted/depthmaps/merged_preview.ply`, {
        method: "GET",
      });
      
      if (!response.ok) {
        throw new Error(`Error fetching pointcloud: ${response.status}`);
      }
      
      return await response.text();
    } catch (error) {
      console.error("Failed to get pointcloud:", error);
      throw error;
    }
  }

  public static async getModel(id: string): Promise<any> {
    try {
      const response = await fetch(`${VITE_API_URL}/api/v1/output/${id}/process/preview/0_0_0.glb`, {
        method: "GET",
      });
      
      if (!response.ok) {
        throw new Error(`Error fetching model: ${response.status}`);
      }
      return await response.arrayBuffer();
    } catch (error) {
      console.error("Failed to get model:", error);
      throw error;
    }
  }
}

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
}: PhotogrammetryCanvasCanvasProps) {

  const [activeLayer, setActiveLayer] = useState<string | null>(null);
  const { data: text_sparse, isPending: isPendingSparse } = useQuery({
    queryFn: () => PhotogrammetryResultService.getReconstruction(pipeline?.id),
    queryKey: ["pipeline-photogrammetry-sparse", pipeline?.id],
  })

  const { data: text_dense, isPending: isPendingDense } = useQuery({
    queryFn: () => PhotogrammetryResultService.getPointcloud(pipeline?.id),
    queryKey: ["pipeline-photogrammetry-dense", pipeline?.id],
  })

  const group = useRef()
  const material = useRef()
  const [data, setData] = useState({
    stage: 'all',
    feature_process_size: 2048,
    depthmap_resolution: 2048,
    force_delete: false,
    auto_resolutions_computation: false,
    processes: 1,
    read_processes: 4,
    depthmap_processes: 1,
    ...pipeline.data,
  })

  const tileset: any = pipeline?.task_result?.tileset
  const download: string = `${pipeline?.task_result?.download}`


  const updateScene = (group: any) => {
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

  const displayPLY = useCallback((text: string, point_size: number) => {
    if (!text || !group.current) {
      console.error("No PLY data or scene available");
      return;
    }

    try {
      const loader = new PLYLoader();
      const geometry = loader.parse(text);
      updateScene(group.current); // Clear previous scene
      geometry.rotateX(-Math.PI / 2);
      const pointMaterial = new THREE.PointsMaterial({
        size: point_size,
        vertexColors: true
      });
      const points = new THREE.Points(geometry, pointMaterial);
      // @ts-ignore
      group.current.add(points);
      const box = new THREE.Box3().setFromObject(points);
      const center = new THREE.Vector3();
      box.getCenter(center);
      points.position.sub(center);
    } catch (error) {
      console.error("Error displaying PLY data:", error);
    }
  }, [text_sparse, text_dense]);

  const handleLayerChange = (value: string) => {
    setActiveLayer(value);

    if (value === "sparse" && typeof text_sparse === "string") {
      displayPLY(text_sparse, 4);
    } else if (value === "dense" && typeof text_dense === "string") {
      displayPLY(text_dense, 0.001);
    } else if (value === "none") {
      updateScene(group.current);
    }
  };

  function handleOnChange(key: string, value: any) {
    const newData = { ...data, [key]: value }
    setData(newData)
  }

  function handleInitializeScene(config: any) {
    group.current = config.group
    material.current = config.pointMaterial
    updateScene(group.current)
  }

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
            <FormLabel fontSize="xs" htmlFor="feature_process_size">
              Feature process size
            </FormLabel>
            <Input
              id="feature_process_size"
              size="xs"
              type="number"
              disabled={data?.auto_resolutions_computation}
              defaultValue={data?.feature_process_size}
              onChange={(event) =>
                handleOnChange("feature_process_size", parseInt(event.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2} >
            <FormLabel fontSize="xs" htmlFor="depthmap_resolution">
              Depth map resolution
            </FormLabel>
            <Input
              id="depthmap_resolution"
              size="xs"
              disabled={data?.auto_resolutions_computation}
              type="number"
              defaultValue={data?.depthmap_resolution}
              onChange={(event) =>
                handleOnChange("depthmap_resolution", parseInt(event.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2} >
            <FormLabel fontSize="xs" htmlFor="processes">
              Processes
            </FormLabel>
            <Input
              id="processes"
              size="xs"
              disabled={data?.auto_resolutions_computation}
              type="number"
              defaultValue={data?.processes}
              onChange={(event) =>
                handleOnChange("processes", parseInt(event.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2} >
            <FormLabel fontSize="xs" htmlFor="read_processes">
              Read processes
            </FormLabel>
            <Input
              id="read_processes"
              size="xs"
              disabled={data?.auto_resolutions_computation}
              type="number"
              defaultValue={data?.read_processes}
              onChange={(event) =>
                handleOnChange("read_processes", parseInt(event.target.value))
              }
            />
          </FormControl>
          <FormControl mt={2} mb={2} >
            <FormLabel fontSize="xs" htmlFor="depthmap_processes">
              Depth map processes
            </FormLabel>
            <Input
              id="depthmap_processes"
              size="xs"
              disabled={data?.auto_resolutions_computation}
              type="number"
              defaultValue={data?.depthmap_processes}
              onChange={(event) =>
                handleOnChange("depthmap_processes", parseInt(event.target.value))
              }
            />
          </FormControl>
          <Flex mt={2}>
            <Checkbox
              id="auto_resolutions_computation"
              size="sm"
              isChecked={data?.auto_resolutions_computation}
              onChange={(event) =>
                handleOnChange("auto_resolutions_computation", event.target.checked)
              }
            >
              Auto compute resources
            </Checkbox>
          </Flex>
          <Flex mt={2} mb={2}>
            <Checkbox
              id="force_delete"
              size="sm"
              isChecked={data?.force_delete || false}
              onChange={(event) =>
                handleOnChange("force_delete", event.target.checked)
              }
            >
              Delete previous process
            </Checkbox>
          </Flex>
          <Divider />
          <Box mt={4} mb={3}>
            <Text fontSize="sm" fontWeight="bold" mb={2}>
              Preview
            </Text>
            <Box
              border="1px"
              borderColor="gray.200"
              borderRadius="md"
              p={2}
              bg="gray.50"
            >
              <Flex justify="flex-end" mb={2}>
                <Button
                  size="xs"
                  colorScheme="gray"
                  variant="outline"
                  leftIcon={<Icon as={FiX} fontSize="10px" />}
                  onClick={() => handleLayerChange("none")}
                  isDisabled={!activeLayer}
                >
                  Clear View
                </Button>
              </Flex>
              <RadioGroup onChange={handleLayerChange} value={activeLayer ?? undefined}>
                <Stack spacing={2}>
                  {text_sparse && !isPendingSparse && (
                    <Radio value="sparse" size="sm" colorScheme="blue">
                      <Text fontSize="xs">
                        Sparse points with camera poses
                      </Text>
                    </Radio>
                  )}
                  {text_dense && !isPendingDense && (
                    <Radio value="dense" size="sm" colorScheme="orange">
                      <Text fontSize="xs">Dense points</Text>
                    </Radio>
                  )}
                </Stack>
              </RadioGroup>
            </Box>
          </Box>
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
