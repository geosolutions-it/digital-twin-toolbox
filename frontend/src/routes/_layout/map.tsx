import { Box, Divider, Flex } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { OpenAPI } from "../../client/core/OpenAPI"

export const Route = createFileRoute("/_layout/map")({
  component: MapStore,
})

function MapStore() {
  return (
    <Box w="100%" pos="relative" h="calc(100vh)" m="0">
      <Flex pos="absolute" w="100%" h="100%">
        <Box w="calc(100% - 74px)" pos="relative">
          <iframe
            title="MapStore Viewer"
            style={{
              position: "absolute",
              width: "100%",
              height: "100%",
              border: "none",
              margin: 0,
              padding: 0,
            }}
            src={`/mapstore/map.html?access_token=${localStorage.getItem(
              "access_token",
            )}&open_api_base=${OpenAPI.BASE}`}
          />
        </Box>
        <Divider orientation="vertical" />
      </Flex>
    </Box>
  )
}
