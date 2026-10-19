import { Box, Flex, Heading, Text } from "@chakra-ui/react"
import type { ReactNode } from "react"

interface PageHeaderProps {
  eyebrow: string
  title: string
  actions?: ReactNode
}

export default function PageHeader({ eyebrow, title, actions }: PageHeaderProps) {
  return (
    <Flex
      position="sticky"
      top={0}
      zIndex={10}
      bg="chakra-body-bg"
      align="center"
      justify="space-between"
      gap={4}
      pt={12}
      pb={6}
    >
      <Box>
        <Text
          fontSize="xs"
          color="gray.500"
          textTransform="uppercase"
          letterSpacing="wide"
        >
          {eyebrow}
        </Text>
        <Heading size="lg">{title}</Heading>
      </Box>
      {actions}
    </Flex>
  )
}
