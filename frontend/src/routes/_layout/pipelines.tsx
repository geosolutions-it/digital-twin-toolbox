import {
  celeryTaskStatusColor,
  celeryTaskStatusLabel,
  isCeleryTaskInProgress,
} from "../../utils/celeryStatus"
import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Badge,
  Box,
  Button,
  Checkbox,
  Container,
  Flex,
  HStack,
  Icon,
  IconButton,
  Input,
  InputGroup,
  InputLeftElement,
  Progress,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import React from "react"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import {
  FiChevronDown,
  FiChevronRight,
  FiDownload,
  FiEdit,
  FiExternalLink,
  FiPlay,
  FiRefreshCw,
  FiSearch,
  FiSettings,
  FiSquare,
  FiTrash,
} from "react-icons/fi"
import { z } from "zod"
import {
  API_BASE,
  deletePipeline,
  processPipelineTask,
  readPipelines,
  readPipelinesOverview,
} from "../../api"
import type {
  PipelineBatchCounts,
  PipelineBatchSummary,
  PipelineOverviewEntry,
} from "../../api/types"
import useCustomToast from "../../hooks/useCustomToast"
import NewBatchModal, {
  type BatchFormValues,
  type PipelineType,
} from "../../components/Pipelines/NewBatchModal"
import PageHeader from "../../components/Common/PageHeader"
import {
  deletePipelineBatch,
  finalizePipelineBatch,
  processPipelineBatchTask,
} from "../../api/pipelineBatch"

const pipelinesSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/pipelines")({
  component: Pipelines,
  validateSearch: (search) => pipelinesSearchSchema.parse(search),
})

interface DeleteProps {
  id: string
  isOpen: boolean
  onClose: () => void
}

const DeleteDialog = ({ id, isOpen, onClose }: DeleteProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const cancelRef = React.useRef<HTMLButtonElement | null>(null)
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm()

  const deleteEntity = async (id: string) => {
    await deletePipeline(id)
  }

  const mutation = useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => {
      showToast("Success", "The Pipeline was deleted successfully.", "success")
      onClose()
    },
    onError: () => {
      showToast(
        "An error occurred.",
        "An error occurred while deleting the Pipeline.",
        "error",
      )
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["pipelines"],
      })
    },
  })

  const onSubmit = async () => {
    mutation.mutate(id)
  }

  return (
    <>
      <AlertDialog
        isOpen={isOpen}
        onClose={onClose}
        leastDestructiveRef={cancelRef}
        size={{ base: "sm", md: "md" }}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent as="form" onSubmit={handleSubmit(onSubmit)}>
            <AlertDialogHeader>Delete Pipeline</AlertDialogHeader>

            <AlertDialogBody>
              Are you sure? You will not be able to undo this action.
            </AlertDialogBody>

            <AlertDialogFooter gap={3}>
              <Button
                ref={cancelRef}
                onClick={onClose}
                isDisabled={isSubmitting}
                size="sm"
                variant="outline"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="outline"
                colorScheme="red"
                type="submit"
                isLoading={isSubmitting}
              >
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </>
  )
}

interface RemoveButtonProps {
  id: string
}

const RemoveButton = ({ id }: RemoveButtonProps) => {
  const deleteModal = useDisclosure()
  return (
    <>
      <Tooltip label="Delete">
        <IconButton
          aria-label="Delete"
          icon={<FiTrash />}
          size="xs"
          variant="ghost"
          colorScheme="red"
          onClick={deleteModal.onOpen}
        />
      </Tooltip>
      <DeleteDialog
        id={id}
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.onClose}
      />
    </>
  )
}

const PER_PAGE = 10

function getOverviewQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      readPipelinesOverview({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
      }),
    queryKey: ["pipelines", "overview", { page }],
  }
}

function StatusCell({ status }: { status?: string | null }) {
  return (
    <Flex direction="column" gap={1} maxW="160px">
      <Badge colorScheme={celeryTaskStatusColor(status)} width="fit-content">
        {celeryTaskStatusLabel(status)}
      </Badge>
      {isCeleryTaskInProgress(status) && (
        <Progress
          size="xs"
          isIndeterminate
          borderRadius="full"
          colorScheme={celeryTaskStatusColor(status)}
        />
      )}
    </Flex>
  )
}

type Pipeline = any

type EditTarget =
  | { kind: "single"; id: string; label: string; type: PipelineType; sampleKey?: string; values: Partial<BatchFormValues> }
  | { kind: "batch"; batchId: string; label: string; type: PipelineType; sampleKey?: string; values: Partial<BatchFormValues> }

function pipelineType(p: Pipeline): PipelineType {
  const t = p?.source?.pipeline
  if (t === "Polygon" || t === "Terrain" || t === "Instance") return t
  return "PointCloud"
}

function dataToValues(d: any): Partial<BatchFormValues> {
  const num = (v: any) => (typeof v === "number" ? String(v) : "")
  // heights may be a scalar or an expression array; keep arrays intact for the editor
  const expr = (v: any) => (Array.isArray(v) ? v : typeof v === "number" ? String(v) : "")
  return {
    sample_radius: d?.sample_radius != null ? String(d.sample_radius) : "",
    colorization_image: d?.colorization_image || "",
    to_ellipsoidal_height: !!d?.to_ellipsoidal_height,
    ground_classification: !!d?.ground_classification,
    lower_limit_height: expr(d?.lower_limit_height),
    upper_limit_height: expr(d?.upper_limit_height),
    remove_bottom_surface: d?.remove_bottom_surface !== false,
    max_features_per_tile: num(d?.max_features_per_tile),
    max_geometric_error: num(d?.max_geometric_error),
    max_error: num(d?.max_error),
    max_zoom: num(d?.max_zoom),
    vertex_normals: d?.vertex_normals !== false,
    water_key: d?.water_key || "",
    model: expr(d?.model) || (typeof d?.model === "string" ? d.model : ""),
    models_prefix: d?.models_prefix || "",
    scale: expr(d?.scale),
    rotation: expr(d?.rotation),
    translate_z: expr(d?.translate_z),
  }
}

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
  if (counts.failed) return { color: "red", label: `Done · ${counts.failed} failed` }
  return { color: "green", label: "Completed" }
}

function RollupBar({ counts }: { counts: PipelineBatchCounts }) {
  const order: (keyof typeof counts)[] = ["success", "running", "ready", "failed"]
  return (
    <Flex h="6px" minW="90px" borderRadius="full" overflow="hidden" bg="gray.100" _dark={{ bg: "gray.700" }}>
      {order.map((k) =>
        counts[k] ? <Box key={k} flex={counts[k]} bg={SEG_COLORS[k]} /> : null,
      )}
    </Flex>
  )
}

type RowAction = "run" | "cancel" | "delete" | "rebuild"
type BatchAction = "run" | "cancel" | "delete" | "rebuild"

interface RowProps {
  pipeline: Pipeline
  selected: Set<string>
  onToggle: (id: string) => void
  onAction: (ids: string[], action: RowAction) => void
  onEdit?: (pipeline: Pipeline) => void
  dim?: boolean
  indent?: boolean
}

function PipelineRow({ pipeline, selected, onToggle, onAction, onEdit, dim, indent }: RowProps) {
  const running = isCeleryTaskInProgress(pipeline.task_status)
  const download = `${pipeline?.task_result?.download}`
  const source = pipeline.source
  const subtitle = source?.key
    ? `s3://…/${source.key}`
    : pipeline.asset_id
      ? "uploaded asset"
      : "no input"
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
          {pipeline.asset_id ? (
            <Link to="/pipeline/$pipelineId" params={{ pipelineId: pipeline.id }}>
              <HStack minW={0}>
                <FiEdit fontSize="14px" />
                <Text fontWeight="600" isTruncated>
                  {pipeline.title}
                </Text>
              </HStack>
            </Link>
          ) : (
            <Text fontWeight="600" isTruncated>
              {pipeline.title}
            </Text>
          )}
          <Text fontSize="xs" color="gray.500" isTruncated>
            {subtitle}
          </Text>
        </Flex>
      </Td>
      <Td>
        <StatusCell status={pipeline.task_status} />
      </Td>
      <Td textAlign="right">
        <HStack spacing={1} justify="flex-end">
          {!pipeline.asset_id && pipeline.task_result?.tileset && (
            <Tooltip label="Open tileset">
              <IconButton
                as="a"
                href={`${API_BASE}${pipeline.task_result.tileset}`}
                target="_blank"
                rel="noreferrer"
                aria-label="Open tileset"
                icon={<FiExternalLink />}
                size="xs"
                variant="ghost"
              />
            </Tooltip>
          )}
          {pipeline.task_result && (
            <Tooltip label="Download 3D Tiles">
              <IconButton
                as="a"
                href={download}
                download={`${pipeline.title}.zip`}
                aria-label="Download 3D Tiles"
                icon={<FiDownload />}
                size="xs"
                variant="ghost"
              />
            </Tooltip>
          )}
          {!pipeline.asset_id && onEdit && (
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

function BatchGroup({
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
  // combined tileset lives at <output_prefix>/tileset.json once every member is done
  const parentUrl =
    allDone && summary.output_prefix
      ? `${API_BASE}/api/v1/${summary.output_prefix}/tileset.json`
      : ""

  // members load lazily and page on their own, so a big folder never floods the top list
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
      const active = batchRunning || data.some((p) => isCeleryTaskInProgress(p.task_status))
      return active ? 1000 : false
    },
  })
  const memberRows = members?.data || []
  const memberTotal = members?.count ?? total
  const memberIds = memberRows.map((p) => p.id)
  const visibleSelected = memberIds.length > 0 && memberIds.every((i) => selected.has(i))
  const innerHasNext = innerPage * PER_PAGE < memberTotal
  const innerHasPrev = innerPage > 1

  return (
    <>
      <Tr bg="blackAlpha.50" _dark={{ bg: "whiteAlpha.100" }}>
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
            <Tooltip label="Rebuild combined tileset">
              <IconButton
                aria-label="Rebuild combined tileset"
                icon={<FiRefreshCw />}
                size="xs"
                variant="ghost"
                onClick={() => onBatchAction(batchId, "rebuild")}
              />
            </Tooltip>
            <Tooltip label="Delete batch">
              <IconButton
                aria-label="Delete batch"
                icon={<FiTrash />}
                size="xs"
                variant="ghost"
                colorScheme="red"
                onClick={() => onBatchAction(batchId, "delete")}
              />
            </Tooltip>
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

function PipelinesTable() {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })

  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [query, setQuery] = React.useState("")
  // folders are collapsed by default; this holds the ones the user opened
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())
  const [editTarget, setEditTarget] = React.useState<EditTarget | null>(null)

  const {
    data: overview,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getOverviewQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
    refetchInterval: (options) => {
      const data = options?.state?.data?.data || []
      const active = data.some((e: PipelineOverviewEntry) =>
        e.kind === "batch"
          ? (e.batch?.counts.running ?? 0) > 0
          : isCeleryTaskInProgress(e.pipeline?.task_status),
      )
      return active ? 1000 : false
    },
  })

  const q = query.toLowerCase()
  const entries = (overview?.data || []).filter((e) =>
    e.kind === "batch"
      ? (e.batch?.label || "").toLowerCase().includes(q)
      : (e.pipeline?.title || "").toLowerCase().includes(q),
  )
  const soloIds = entries
    .filter((e) => e.kind === "pipeline" && e.pipeline)
    .map((e) => e.pipeline!.id)
  const total = overview?.count ?? 0
  const hasNextPage = page * PER_PAGE < total
  const hasPreviousPage = page > 1
  const showPager = hasNextPage || hasPreviousPage
  const allSelected = soloIds.length > 0 && soloIds.every((id) => selected.has(id))

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getOverviewQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const toggleAll = () =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (soloIds.every((id) => next.has(id))) soloIds.forEach((id) => next.delete(id))
      else soloIds.forEach((id) => next.add(id))
      return next
    })

  const toggleMany = (ids: string[], select: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => (select ? next.add(id) : next.delete(id)))
      return next
    })

  const toggleOpen = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const bulkDelete = useMutation({
    mutationFn: async () => {
      for (const id of Array.from(selected)) {
        await deletePipeline(id)
      }
    },
    onSuccess: () => {
      showToast("Deleted", `Removed ${selected.size} pipeline(s).`, "success")
      setSelected(new Set())
    },
    onError: () => {
      showToast("An error occurred.", "Could not delete the selection.", "error")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })

  const act = useMutation({
    mutationFn: async ({ ids, action }: { ids: string[]; action: RowAction }) => {
      if (action === "rebuild") {
        await finalizePipelineBatch(ids[0])
        return
      }
      for (const id of ids) {
        try {
          if (action === "delete") await deletePipeline(id)
          else await processPipelineTask(id, action)
        } catch {
          // skip rows the action does not apply to
        }
      }
    },
    onSuccess: (_d, { action }) => {
      if (action === "rebuild") showToast("Rebuilding", "Combined tileset is being rebuilt.", "success")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
  const onAction = (ids: string[], action: RowAction) => act.mutate({ ids, action })

  const batchAct = useMutation({
    mutationFn: async ({ batchId, action }: { batchId: string; action: BatchAction }) => {
      if (action === "rebuild") return finalizePipelineBatch(batchId)
      if (action === "delete") return deletePipelineBatch(batchId)
      // run/cancel the whole batch server-side, regardless of which page is loaded
      return processPipelineBatchTask(batchId, action)
    },
    onSuccess: (_d, { action }) => {
      if (action === "rebuild") showToast("Rebuilding", "Combined tileset is being rebuilt.", "success")
      if (action === "delete") showToast("Deleted", "Batch removed.", "success")
    },
    onError: () => {
      showToast("An error occurred.", "Could not apply the batch action.", "error")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
  const onBatchAction = (batchId: string, action: BatchAction) => batchAct.mutate({ batchId, action })

  const editPipeline = (p: Pipeline) =>
    setEditTarget({ kind: "single", id: p.id, label: p.title, type: pipelineType(p), sampleKey: p?.source?.key, values: dataToValues(p.data) })
  const editBatch = (summary: PipelineBatchSummary) =>
    setEditTarget({
      kind: "batch",
      batchId: summary.batch_id,
      label: summary.label,
      type: (summary.pipeline as PipelineType) || "PointCloud",
      sampleKey: summary.sample_key || undefined,
      values: dataToValues(summary.data),
    })

  const bulkAction = useMutation({
    mutationFn: async (actionType: "run" | "cancel") => {
      for (const id of Array.from(selected)) {
        try {
          await processPipelineTask(id, actionType)
        } catch {
          // skip rows the action does not apply to (already running, nothing to cancel)
        }
      }
    },
    onSuccess: (_d, actionType) => {
      showToast(actionType === "run" ? "Started" : "Cancelled", `${selected.size} job(s).`, "success")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })

  return (
    <>
      <InputGroup maxW="320px" mb={4}>
        <InputLeftElement pointerEvents="none">
          <Icon as={FiSearch} color="gray.400" />
        </InputLeftElement>
        <Input
          placeholder="Filter by title"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </InputGroup>

      <TableContainer w="100%">
        <Table variant="simple" size="sm" width="100%">
          <Thead>
            <Tr>
              <Th width="40px">
                <Checkbox
                  isChecked={allSelected}
                  onChange={toggleAll}
                  aria-label="Select all"
                />
              </Th>
              <Th>Job</Th>
              <Th width="200px">Status</Th>
              <Th width="160px" />
            </Tr>
          </Thead>
          {isPending ? (
            <Tbody>
              <Tr>
                {new Array(4).fill(null).map((_, index) => (
                  <Td key={index}>
                    <SkeletonText noOfLines={1} paddingBlock="16px" />
                  </Td>
                ))}
              </Tr>
            </Tbody>
          ) : (
            <Tbody>
              {entries.map((entry) =>
                entry.kind === "batch" && entry.batch ? (
                  <BatchGroup
                    key={entry.batch.batch_id}
                    summary={entry.batch}
                    open={expanded.has(entry.batch.batch_id)}
                    onToggleOpen={toggleOpen}
                    selected={selected}
                    onToggle={toggle}
                    onToggleMany={toggleMany}
                    onBatchAction={onBatchAction}
                    onRowAction={onAction}
                    onEditBatch={editBatch}
                  />
                ) : entry.pipeline ? (
                  <PipelineRow
                    key={entry.pipeline.id}
                    pipeline={entry.pipeline}
                    selected={selected}
                    onToggle={toggle}
                    onAction={onAction}
                    onEdit={editPipeline}
                    dim={isPlaceholderData}
                  />
                ) : null,
              )}
            </Tbody>
          )}
        </Table>
      </TableContainer>

      {showPager && (
        <Flex
          position="sticky"
          bottom={0}
          zIndex={10}
          bg="chakra-body-bg"
          gap={4}
          alignItems="center"
          py={4}
          justifyContent="center"
        >
          <Button size="sm" onClick={() => setPage(page - 1)} isDisabled={!hasPreviousPage}>
            Previous
          </Button>
          <span>Page {page}</span>
          <Button size="sm" isDisabled={!hasNextPage} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </Flex>
      )}

      {selected.size > 0 && (
        <Flex
          position="fixed"
          bottom={6}
          left="50%"
          transform="translateX(-50%)"
          zIndex={20}
          bg="white"
          _dark={{ bg: "gray.800", borderColor: "gray.600" }}
          border="1px solid"
          borderColor="gray.200"
          boxShadow="lg"
          borderRadius="xl"
          px={4}
          py={3}
          gap={3}
          alignItems="center"
        >
          <Text fontWeight="700">{selected.size} selected</Text>
          <Button
            size="sm"
            colorScheme="green"
            variant="outline"
            leftIcon={<FiPlay />}
            isLoading={bulkAction.isPending && bulkAction.variables === "run"}
            onClick={() => bulkAction.mutate("run")}
          >
            Run
          </Button>
          <Button
            size="sm"
            colorScheme="orange"
            variant="outline"
            leftIcon={<FiSquare />}
            isLoading={bulkAction.isPending && bulkAction.variables === "cancel"}
            onClick={() => bulkAction.mutate("cancel")}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            colorScheme="red"
            variant="outline"
            leftIcon={<FiTrash />}
            isLoading={bulkDelete.isPending}
            onClick={() => bulkDelete.mutate()}
          >
            Delete
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </Flex>
      )}

      <NewBatchModal
        isOpen={!!editTarget}
        onClose={() => setEditTarget(null)}
        label={editTarget?.label}
        pipelineType={editTarget?.type}
        editSampleKey={editTarget?.sampleKey}
        initialValues={editTarget?.values}
        editPipelineId={editTarget?.kind === "single" ? editTarget.id : undefined}
        editBatchId={editTarget?.kind === "batch" ? editTarget.batchId : undefined}
      />
    </>
  )
}

function Pipelines() {
  return (
    <Container maxW="full">
      <PageHeader eyebrow="Processing" title="Pipelines" />
      <PipelinesTable />
    </Container>
  )
}
