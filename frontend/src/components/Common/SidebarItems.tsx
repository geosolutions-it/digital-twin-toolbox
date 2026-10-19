import { Box, Flex, Icon, Text, useColorModeValue } from "@chakra-ui/react"
import { Link } from "@tanstack/react-router"
import { FiBox, FiFile, FiMap } from "react-icons/fi"

interface SidebarItemsProps {
  onClose?: () => void
}

const SidebarItems = ({ onClose }: SidebarItemsProps) => {
  const textColor = useColorModeValue("ui.main", "ui.light")
  const bgActive = useColorModeValue("#E2E8F0", "#4A5568")

  const items = [
    { icon: FiFile, title: "Assets", path: "/assets" },
    { icon: FiBox, title: "Pipelines", path: "/pipelines" },
    { icon: FiMap, title: "Map", path: "/map" },
  ]

  const listItems = items.map(({ icon, title, path }) => (
    <Flex
      as={Link}
      to={path}
      w="100%"
      p={2}
      key={title}
      activeProps={{
        style: {
          background: bgActive,
          borderRadius: "12px",
        },
      }}
      color={textColor}
      onClick={onClose}
    >
      <Icon as={icon} alignSelf="center" />
      <Text ml={2}>{title}</Text>
    </Flex>
  ))

  return (
    <>
      <Box>{listItems}</Box>
    </>
  )
}

export default SidebarItems
