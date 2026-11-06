import { HStack, Icon, Switch, Tooltip, useColorMode } from "@chakra-ui/react"
import { FiMoon, FiSun } from "react-icons/fi"

const Appearance = () => {
  const { colorMode, toggleColorMode } = useColorMode()
  const dark = colorMode === "dark"

  return (
    <Tooltip
      label={dark ? "Switch to light mode" : "Switch to dark mode"}
      placement="right"
    >
      <HStack spacing={2} p={2} w="fit-content">
        <Icon as={FiSun} opacity={dark ? 0.5 : 1} />
        <Switch
          isChecked={dark}
          onChange={toggleColorMode}
          colorScheme="teal"
          aria-label="Dark mode"
        />
        <Icon as={FiMoon} opacity={dark ? 1 : 0.5} />
      </HStack>
    </Tooltip>
  )
}

export default Appearance
