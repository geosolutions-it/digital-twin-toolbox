import {
  Badge,
  Box,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  Progress,
  Text,
} from "@chakra-ui/react"
import React from "react"
import usePipelineLog from "../../hooks/usePipelineLog"
import {
  celeryTaskStatusColor,
  celeryTaskStatusLabel,
  isCeleryTaskInProgress,
} from "../../utils/celeryStatus"

const LEVEL_COLOR: Record<string, string> = {
  WARNING: "orange.400",
  ERROR: "red.400",
  CRITICAL: "red.400",
}

function time(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour12: false })
}

interface LogsDrawerProps {
  pipelineId: string
  title: string
  status?: string | null
  stage?: string | null
  isOpen: boolean
  onClose: () => void
}

export default function LogsDrawer({
  pipelineId,
  title,
  status,
  stage,
  isOpen,
  onClose,
}: LogsDrawerProps) {
  const running = isCeleryTaskInProgress(status)
  const { lines, loaded, failed } = usePipelineLog(pipelineId, {
    enabled: isOpen,
    running,
  })
  const scroller = React.useRef<HTMLDivElement | null>(null)
  const follow = React.useRef(true)

  React.useEffect(() => {
    const el = scroller.current
    if (el && follow.current && lines.length) el.scrollTop = el.scrollHeight
  }, [lines.length])

  const onScroll = () => {
    const el = scroller.current
    if (el)
      follow.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 24
  }

  return (
    <Drawer isOpen={isOpen} onClose={onClose} placement="right" size="xl">
      <DrawerOverlay />
      <DrawerContent>
        <DrawerCloseButton />
        <DrawerHeader pr={12}>
          <Text
            fontSize="xs"
            color="gray.500"
            fontWeight="600"
            textTransform="uppercase"
          >
            Logs
          </Text>
          <Text isTruncated>{title}</Text>
          <Flex align="center" gap={3} mt={2} minW={0}>
            <Badge colorScheme={celeryTaskStatusColor(status)} flexShrink={0}>
              {celeryTaskStatusLabel(status)}
            </Badge>
            {running && stage && (
              <Text
                fontSize="sm"
                fontWeight="400"
                color="gray.500"
                isTruncated
                title={stage}
              >
                {stage}
              </Text>
            )}
          </Flex>
          {running && (
            <Progress
              size="xs"
              isIndeterminate
              borderRadius="full"
              colorScheme={celeryTaskStatusColor(status)}
              mt={2}
            />
          )}
        </DrawerHeader>
        <DrawerBody p={0} display="flex" flexDirection="column" minH={0}>
          <Box
            ref={scroller}
            onScroll={onScroll}
            flex={1}
            overflowY="auto"
            px={6}
            pb={6}
            fontFamily="mono"
            fontSize="xs"
          >
            {failed && (
              <Text color="red.400" mb={2}>
                Could not load the log.
              </Text>
            )}
            {loaded && !lines.length && !failed && (
              <Text color="gray.500">
                {running
                  ? "Waiting for the first lines…"
                  : "No log for this job."}
              </Text>
            )}
            {lines.map((line) => (
              <Box key={line.id} display="flex" gap={3} py="1px">
                <Text as="span" color="gray.500" flexShrink={0}>
                  {time(line.created_at)}
                </Text>
                <Text
                  as="span"
                  whiteSpace="pre-wrap"
                  wordBreak="break-word"
                  color={LEVEL_COLOR[line.level]}
                  fontWeight={line.stage ? "700" : undefined}
                >
                  {line.message}
                </Text>
              </Box>
            ))}
          </Box>
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
