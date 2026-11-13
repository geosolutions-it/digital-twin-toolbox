import {
  Badge,
  Checkbox,
  Flex,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Progress,
  Td,
  Text,
  Tooltip,
  Tr,
  useDisclosure,
} from "@chakra-ui/react"
import {
  FiDownload,
  FiExternalLink,
  FiFileText,
  FiPlay,
  FiSettings,
  FiSquare,
  FiTerminal,
} from "react-icons/fi"
import { API_BASE } from "../../api"
import type { PipelinePublic } from "../../api/types"
import {
  celeryTaskStatusColor,
  celeryTaskStatusLabel,
  isCeleryTaskInProgress,
} from "../../utils/celeryStatus"
import { RemoveButton } from "./DeleteDialog"
import LogsDrawer from "./LogsDrawer"
import {
  type Artifact,
  type RowAction,
  type TaskResult,
  sourceOf,
  zipName,
} from "./pipelineData"

function StatusCell({
  status,
  stage,
}: { status?: string | null; stage?: string | null }) {
  const running = isCeleryTaskInProgress(status)
  return (
    <Flex direction="column" gap={1} maxW="180px">
      <Badge colorScheme={celeryTaskStatusColor(status)} width="fit-content">
        {celeryTaskStatusLabel(status)}
      </Badge>
      {running && (
        <Progress
          size="xs"
          isIndeterminate
          borderRadius="full"
          colorScheme={celeryTaskStatusColor(status)}
        />
      )}
      {running && stage && (
        <Text fontSize="xs" color="gray.500" isTruncated title={stage}>
          {stage}
        </Text>
      )}
    </Flex>
  )
}

function LogsButton({ pipeline }: { pipeline: PipelinePublic }) {
  const logs = useDisclosure()
  return (
    <>
      <Tooltip label="Logs">
        <IconButton
          aria-label="Logs"
          icon={<FiTerminal />}
          size="xs"
          variant="ghost"
          onClick={logs.onOpen}
        />
      </Tooltip>
      <LogsDrawer
        key={pipeline.task_id}
        pipelineId={pipeline.id}
        title={pipeline.title}
        status={pipeline.task_status}
        stage={pipeline.stage}
        isOpen={logs.isOpen}
        onClose={logs.onClose}
      />
    </>
  )
}

function artifactSize(bytes?: number) {
  if (!bytes) return ""
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  )
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function ArtifactsMenu({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <Menu isLazy placement="bottom-end">
      <Tooltip label="Other outputs">
        <MenuButton
          as={IconButton}
          aria-label="Other outputs"
          icon={<FiFileText />}
          size="xs"
          variant="ghost"
        />
      </Tooltip>
      <MenuList fontSize="sm">
        {artifacts.map((a) => (
          <MenuItem
            key={a.name}
            as="a"
            href={`${API_BASE}${a.url}`}
            download={a.name}
          >
            <Text fontFamily="mono" fontSize="xs" mr={3}>
              {a.name}
            </Text>
            <Text fontSize="xs" color="gray.500" ml="auto">
              {artifactSize(a.size)}
            </Text>
          </MenuItem>
        ))}
      </MenuList>
    </Menu>
  )
}

interface RowProps {
  pipeline: PipelinePublic
  selected: Set<string>
  onToggle: (id: string) => void
  onAction: (ids: string[], action: RowAction) => void
  onEdit?: (pipeline: PipelinePublic) => void
  dim?: boolean
  indent?: boolean
}

export function PipelineRow({
  pipeline,
  selected,
  onToggle,
  onAction,
  onEdit,
  dim,
  indent,
}: RowProps) {
  const running = isCeleryTaskInProgress(pipeline.task_status)
  const result = pipeline.task_result as TaskResult | null
  const download = `${API_BASE}${result?.download}`
  const source = sourceOf(pipeline)
  const subtitle = source?.key ? `s3://…/${source.key}` : "no input"
  const isSel = selected.has(pipeline.id)
  return (
    <Tr
      opacity={dim ? 0.5 : 1}
      bg={isSel ? "blue.50" : undefined}
      _dark={{ bg: isSel ? "blue.900" : undefined }}
    >
      <Td pl={indent ? 10 : undefined}>
        <Checkbox
          isChecked={isSel}
          onChange={() => onToggle(pipeline.id)}
          aria-label={`Select ${pipeline.title}`}
        />
      </Td>
      <Td maxW={0}>
        <Flex direction="column" gap={0.5} minW={0}>
          <Text fontWeight="600" isTruncated>
            {pipeline.title}
          </Text>
          <Text fontSize="xs" color="gray.500" isTruncated>
            {subtitle}
          </Text>
        </Flex>
      </Td>
      <Td>
        <StatusCell status={pipeline.task_status} stage={pipeline.stage} />
      </Td>
      <Td textAlign="right">
        <HStack spacing={1} justify="flex-end">
          {pipeline.task_id && <LogsButton pipeline={pipeline} />}
          {!!result?.artifacts?.length && (
            <ArtifactsMenu artifacts={result.artifacts} />
          )}
          {result?.tileset && (
            <Tooltip label="Open tileset">
              <IconButton
                as="a"
                href={`${API_BASE}${result.tileset}`}
                target="_blank"
                rel="noreferrer"
                aria-label="Open tileset"
                icon={<FiExternalLink />}
                size="xs"
                variant="ghost"
              />
            </Tooltip>
          )}
          {result && (
            <Tooltip label="Download 3D Tiles">
              <IconButton
                as="a"
                href={download}
                download={`${zipName(pipeline.title)}.zip`}
                aria-label="Download 3D Tiles"
                icon={<FiDownload />}
                size="xs"
                variant="ghost"
              />
            </Tooltip>
          )}
          {onEdit && (
            <Tooltip label="Adjust parameters">
              <IconButton
                aria-label="Adjust parameters"
                icon={<FiSettings />}
                size="xs"
                variant="ghost"
                onClick={() => onEdit(pipeline)}
              />
            </Tooltip>
          )}
          {running ? (
            <Tooltip label="Cancel">
              <IconButton
                aria-label="Cancel"
                icon={<FiSquare />}
                size="xs"
                variant="ghost"
                colorScheme="orange"
                onClick={() => onAction([pipeline.id], "cancel")}
              />
            </Tooltip>
          ) : (
            <Tooltip label="Run">
              <IconButton
                aria-label="Run"
                icon={<FiPlay />}
                size="xs"
                variant="ghost"
                colorScheme="green"
                onClick={() => onAction([pipeline.id], "run")}
              />
            </Tooltip>
          )}
          <RemoveButton id={pipeline.id} />
        </HStack>
      </Td>
    </Tr>
  )
}
