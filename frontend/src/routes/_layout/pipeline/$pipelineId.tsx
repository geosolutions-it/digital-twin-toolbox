import { Box, Divider, Flex } from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { PipelinesService } from "../../../client"
import { hideUserSections } from "../../../utils"
import PointCloudCanvas from "../../../components/Viewer/PointCloudCanvas"
// Other pipeline viewers hidden for now (point-cloud focus):
// import PointGeometryCanvas from "../../../components/Viewer/PointGeometryCanvas"
// import PolygonGeometryCanvas from "../../../components/Viewer/PolygonGeometryCanvas"
// import PhotogrammetryCanvas from "../../../components/Viewer/PhotogrammetryCanvas"
// import MeshCanvas from "../../../components/Viewer/MeshCanvas"
import { isCeleryTaskInProgress } from "../../../utils/celeryStatus"

export const Route = createFileRoute("/_layout/pipeline/$pipelineId")({
  component: Pipeline,
})

function Pipeline() {
  const { pipelineId } = Route.useParams()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryFn: () => PipelinesService.readPipeline({ id: pipelineId }),
    queryKey: ["pipeline", pipelineId],
    refetchInterval: (options) => {
      return isCeleryTaskInProgress(options?.state?.data?.task_status)
        ? 1000
        : false
    },
  })

  function handleOnUpdate(data: any) {
    PipelinesService.updatePipeline({
      id: pipelineId,
      requestBody: { data },
    }).then(() =>
      queryClient.invalidateQueries({ queryKey: ["pipeline", pipelineId] }),
    )
  }

  function handleOnRun(data: any) {
    PipelinesService.updatePipeline({ id: pipelineId, requestBody: { data } })
      .then(() =>
        PipelinesService.processPipelineTask({
          id: pipelineId,
          actionType: "run",
        }),
      )
      .then(() =>
        queryClient.invalidateQueries({ queryKey: ["pipeline", pipelineId] }),
      )
  }

  function handleOnCancel() {
    PipelinesService.processPipelineTask({
      id: pipelineId,
      actionType: "cancel",
    }).then(() =>
      queryClient.invalidateQueries({ queryKey: ["pipeline", pipelineId] }),
    )
  }

  const assetId = `${data?.asset_id || ""}`

  if (!assetId) {
    return "This pipeline is not connected to an asset"
  }

  return (
    <Box w="100%" pos="relative" h="calc(var(--dtt-vh))" m="0">
      <Flex pos="absolute" w="100%" h="100%">
        <Box
          w={hideUserSections() ? "100%" : "calc(100% - 74px)"}
          pos="relative"
        >
          <Flex pos="absolute" w="100%" h="100%">
        {data?.asset?.geometry_type === "PointCloud" ? (
          <PointCloudCanvas
            assetId={assetId}
            pipeline={data}
            onUpdate={handleOnUpdate}
            onRun={handleOnRun}
            onCancel={handleOnCancel}
          />
        ) : null}
        {/* Point / Polygon / Photogrammetry / Mesh viewers hidden for now (point-cloud focus) */}
          </Flex>
        </Box>
        <Divider orientation="vertical" />
      </Flex>
    </Box>
  )
}
