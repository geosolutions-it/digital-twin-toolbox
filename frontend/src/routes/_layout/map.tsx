import { Box, Flex, Spinner } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, lazy } from "react"

// Lazy so the Cesium chunk only loads when the Map tab is opened.
const CesiumMap = lazy(() => import("../../components/Viewer/CesiumMap"))

export const Route = createFileRoute("/_layout/map")({
  component: MapPage,
})

function MapPage() {
  return (
    <Box w="100%" h="calc(var(--dtt-vh))" pos="relative" m="0">
      <Suspense
        fallback={
          <Flex w="100%" h="100%" align="center" justify="center">
            <Spinner />
          </Flex>
        }
      >
        <CesiumMap />
      </Suspense>
    </Box>
  )
}
