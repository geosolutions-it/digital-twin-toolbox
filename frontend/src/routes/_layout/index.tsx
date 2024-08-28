import { Container, Flex, Heading, Image, Link, Text } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import Logo from "/assets/images/logo.svg"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

function Dashboard() {
  return (
    <>
      <Container maxW="full">
        <Heading size="2xl" textAlign={{ base: "center", md: "left" }} pt={12}>
          <Flex alignItems="center">
            <Image
              src={Logo}
              alt="Digital Twin Toolbox logo"
              height="48px"
              maxW="2xs"
              alignSelf="center"
              mr={2}
            />
            Digital Twin Toolbox
          </Flex>
        </Heading>
        <Text pt={8} maxW="70ch">
          This project collects different tools/libraries and workflows inside a
          docker environment to generate 3D Tiles from common data sources such
          as Shapefiles and LAS files.
        </Text>
        <Text pt={8} maxW="70ch">
          Extensive documentation about this project can be found in the{" "}
          <Link
            color="ui.success"
            href="https://github.com/geosolutions-it/digital-twin-toolbox/wiki"
          >
            wiki
          </Link>{" "}
          page (see the Table of Contents).
        </Text>
      </Container>
    </>
  )
}
