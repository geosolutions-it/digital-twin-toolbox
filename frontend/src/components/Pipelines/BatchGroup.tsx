import {
  Badge,
  Box,
  Button,
  Checkbox,
  Flex,
  HStack,
  Icon,
  IconButton,
  SkeletonText,
  Td,
  Text,
  Tooltip,
  Tr,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import React from "react"
import {
  FiChevronDown,
  FiChevronRight,
  FiDownload,
  FiExternalLink,
  FiPlay,
  FiRefreshCw,
  FiSettings,
  FiSquare,
} from "react-icons/fi"
import { API_BASE, readPipelines } from "../../api"
import type { PipelineBatchCounts, PipelineBatchSummary } from "../../api/types"
import { isCeleryTaskInProgress } from "../../utils/celeryStatus"
import { RemoveButton } from "./DeleteDialog"
import { PipelineRow } from "./PipelineRow"
import {
  type BatchAction,
  PER_PAGE,
  type RowAction,
  zipName,
} from "./pipelineData"

const SEG_COLORS: Record<string, string> = {
  success: "green.400",
  running: "yellow.400",
  ready: "gray.300",
  failed: "red.400",
}

function batchState(counts: PipelineBatchCounts, total: number) {
  if (counts.running)
    return {
      color: "yellow",
      label: `Running ${Math.round((100 * counts.success) / total)}%`,
    }
  if (counts.ready) return { color: "blue", label: "Queued" }
  if (counts.failed)
    return { color: "red", label: `Done · ${counts.failed} failed` }
  return { color: "green", label: "Completed" }
}

function RollupBar({ counts }: { counts: PipelineBatchCounts }) {
  const order: (keyof typeof counts)[] = [
    "success",
    "running",
    "ready",
    "failed",
  ]
  return (
    <Flex
      h="6px"
      minW="90px"
      borderRadius="full"
      overflow="hidden"
      bg="gray.100"
      _dark={{ bg: "gray.700" }}
    >
      {order.map((k) =>
        counts[k] ? <Box key={k} flex={counts[k]} bg={SEG_COLORS[k]} /> : null,
      )}
    </Flex>
  )
}

interface BatchGroupProps {
  summary: PipelineBatchSummary
  open: boolean
  onToggleOpen: (id: string) => void
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleMany: (ids: string[], select: boolean) => void
  onBatchAction: (batchId: string, action: BatchAction) => void
  onRowAction: (ids: string[], action: RowAction) => void
  onEditBatch?: (summary: PipelineBatchSummary) => void
}

export function BatchGroup({
  summary,
  open,
  onToggleOpen,
  selected,
  onToggle,
  onToggleMany,
  onBatchAction,
  onRowAction,
  onEditBatch,
}: BatchGroupProps) {
  const batchId = summary.batch_id
  const counts = summary.counts
  const total = summary.total
  const state = batchState(counts, total || 1)
  const batchRunning = counts.running > 0
  const allDone = total > 0 && counts.success === total
  // combined tileset lives at <output_url>/tileset.json once every member is done
  const outputUrl = summary.output_url
  const parentUrl =
    allDone && outputUrl ? `${API_BASE}${outputUrl}/tileset.json` : ""
  const parentDownload =
    allDone && outputUrl ? `${API_BASE}${outputUrl}/download.zip` : ""

  const [innerPage, setInnerPage] = React.useState(1)
  const { data: members, isPending: membersPending } = useQuery({
    queryKey: ["pipelines", "batch", batchId, { page: innerPage }],
    queryFn: () =>
      readPipelines({
        batch_id: batchId,
        skip: (innerPage - 1) * PER_PAGE,
        limit: PER_PAGE,
      }),
    enabled: open,
    placeholderData: (prev) => prev,
    refetchInterval: (query) => {
      const data = query.state.data?.data || []
      const active =
        batchRunning || data.some((p) => isCeleryTaskInProgress(p.task_status))
      return active ? 1000 : false
    },
  })
  const memberRows = members?.data || []
  const memberTotal = members?.count ?? total
  const memberIds = memberRows.map((p) => p.id)
  const visibleSelected =
    memberIds.length > 0 && memberIds.every((i) => selected.has(i))
  const innerHasNext = innerPage * PER_PAGE < memberTotal
  const innerHasPrev = innerPage > 1

  return (
    <>
      <Tr>
        <Td>
          <Checkbox
            isChecked={visibleSelected}
            onChange={() => onToggleMany(memberIds, !visibleSelected)}
            isDisabled={memberIds.length === 0}
            aria-label={`Select visible members of ${summary.label}`}
          />
        </Td>
        <Td maxW={0}>
          <Flex align="center" gap={2} minW={0}>
            <Box
              as="button"
              type="button"
              onClick={() => onToggleOpen(batchId)}
              aria-label="Toggle batch"
              display="flex"
              flexShrink={0}
            >
              <Icon as={open ? FiChevronDown : FiChevronRight} />
            </Box>
            <Flex direction="column" gap={0.5} minW={0}>
              <Text fontWeight="700" isTruncated>
                {summary.label}
              </Text>
              {summary.source && (
                <Text fontSize="xs" color="gray.500" isTruncated>
                  {summary.source}
                </Text>
              )}
            </Flex>
          </Flex>
        </Td>
        <Td>
          <Flex align="center" gap={3}>
            <Badge colorScheme={state.color} width="fit-content">
              {state.label}
            </Badge>
            <Flex direction="column" gap={1} minW="90px">
              <Text fontSize="xs" color="gray.500">
                {counts.success}/{total} done
              </Text>
              <RollupBar counts={counts} />
            </Flex>
          </Flex>
        </Td>
        <Td textAlign="right">
          <HStack spacing={1} justify="flex-end">
            <Tooltip label="Rebuild combined tileset">
              <IconButton
                aria-label="Rebuild combined tileset"
                icon={<FiRefreshCw />}
                size="xs"
                variant="ghost"
                onClick={() => onBatchAction(batchId, "rebuild")}
              />
            </Tooltip>
            {parentUrl && (
              <Tooltip label="Open combined tileset">
                <IconButton
                  as="a"
                  href={parentUrl}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="Open combined tileset"
                  icon={<FiExternalLink />}
                  size="xs"
                  variant="ghost"
                />
              </Tooltip>
            )}
            {parentDownload && (
              <Tooltip label="Download combined 3D Tiles">
                <IconButton
                  as="a"
                  href={parentDownload}
                  download={`${zipName(summary.label)}.zip`}
                  aria-label="Download combined 3D Tiles"
                  icon={<FiDownload />}
                  size="xs"
                  variant="ghost"
                />
              </Tooltip>
            )}
            {onEditBatch && (
              <Tooltip label="Adjust parameters">
                <IconButton
                  aria-label="Adjust parameters"
                  icon={<FiSettings />}
                  size="xs"
                  variant="ghost"
                  onClick={() => onEditBatch(summary)}
                />
              </Tooltip>
            )}
            {batchRunning ? (
              <Tooltip label="Cancel batch">
                <IconButton
                  aria-label="Cancel batch"
                  icon={<FiSquare />}
                  size="xs"
                  variant="ghost"
                  colorScheme="orange"
                  onClick={() => onBatchAction(batchId, "cancel")}
                />
              </Tooltip>
            ) : (
              <Tooltip label="Run batch">
                <IconButton
                  aria-label="Run batch"
                  icon={<FiPlay />}
                  size="xs"
                  variant="ghost"
                  colorScheme="green"
                  onClick={() => onBatchAction(batchId, "run")}
                />
              </Tooltip>
            )}
            <RemoveButton id={batchId} batch />
          </HStack>
        </Td>
      </Tr>
      {open && membersPending && (
        <Tr>
          <Td />
          <Td colSpan={3}>
            <SkeletonText noOfLines={1} paddingBlock="12px" />
          </Td>
        </Tr>
      )}
      {open &&
        memberRows.map((p) => (
          <PipelineRow
            key={p.id}
            pipeline={p}
            selected={selected}
            onToggle={onToggle}
            onAction={onRowAction}
            indent
          />
        ))}
      {open && (innerHasNext || innerHasPrev) && (
        <Tr>
          <Td />
          <Td colSpan={3}>
            <Flex gap={3} align="center" py={1} pl={6}>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setInnerPage((n) => Math.max(1, n - 1))}
                isDisabled={!innerHasPrev}
              >
                Previous
              </Button>
              <Text fontSize="xs" color="gray.500">
                Page {innerPage} · {memberTotal} files
              </Text>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setInnerPage((n) => n + 1)}
                isDisabled={!innerHasNext}
              >
                Next
              </Button>
            </Flex>
          </Td>
        </Tr>
      )}
    </>
  )
}
