import { Box, Flex } from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { PipelinesService } from "../../../client"
import PointCloudCanvas from "../../../components/Viewer/PointCloudCanvas"
import PointGeometryCanvas from "../../../components/Viewer/PointGeometryCanvas"
import PolygonGeometryCanvas from "../../../components/Viewer/PolygonGeometryCanvas"

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
      return options?.state?.data?.task_status === "PENDING" ? 1000 : false
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
        {data?.asset?.geometry_type === "PointCloud" ? (
          <PointCloudCanvas
            assetId={assetId}
            pipeline={data}
            onUpdate={handleOnUpdate}
            onRun={handleOnRun}
            onCancel={handleOnCancel}
          />
        ) : null}
        {data?.asset?.geometry_type === "Point" ? (
          <PointGeometryCanvas
            assetId={assetId}
            pipeline={data}
            onUpdate={handleOnUpdate}
            onRun={handleOnRun}
            onCancel={handleOnCancel}
          />
        ) : null}
        {data?.asset?.geometry_type === "Polygon" ? (
          <PolygonGeometryCanvas
            assetId={assetId}
            pipeline={data}
            onUpdate={handleOnUpdate}
            onRun={handleOnRun}
            onCancel={handleOnCancel}
          />
        ) : null}
      </Flex>
    </Box>
  )
}
