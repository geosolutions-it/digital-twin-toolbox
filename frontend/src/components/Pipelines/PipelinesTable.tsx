import {
  Button,
  Checkbox,
  Flex,
  Icon,
  Input,
  InputGroup,
  InputLeftElement,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import React, { useEffect } from "react"
import { FiPlay, FiSearch, FiSquare, FiTrash } from "react-icons/fi"
import {
  deletePipeline,
  processPipelineTask,
  readPipelinesOverview,
} from "../../api"
import {
  finalizePipelineBatch,
  processPipelineBatchTask,
} from "../../api/pipelineBatch"
import type {
  PipelineBatchSummary,
  PipelineOverviewEntry,
  PipelinePublic,
  PipelineType,
} from "../../api/types"
import useCustomToast from "../../hooks/useCustomToast"
import { isCeleryTaskInProgress } from "../../utils/celeryStatus"
import { BatchGroup } from "./BatchGroup"
import PipelineModal from "./PipelineModal"
import { PipelineRow } from "./PipelineRow"
import { type PipelineFormValues, formValuesFromConfig } from "./forms"
import {
  type BatchAction,
  PER_PAGE,
  type RowAction,
  pipelineType,
} from "./pipelineData"

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

type EditTarget =
  | {
      kind: "single"
      id: string
      label: string
      type: PipelineType
      sampleKey?: string
      input?: string
      values: Partial<PipelineFormValues>
    }
  | {
      kind: "batch"
      batchId: string
      label: string
      type: PipelineType
      sampleKey?: string
      input?: string
      values: Partial<PipelineFormValues>
    }

export default function PipelinesTable({
  page,
  onPageChange: setPage,
}: {
  page: number
  onPageChange: (page: number) => void
}) {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()

  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [query, setQuery] = React.useState("")
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
  const allSelected =
    soloIds.length > 0 && soloIds.every((id) => selected.has(id))

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
      const select = !soloIds.every((id) => next.has(id))
      for (const id of soloIds) {
        if (select) next.add(id)
        else next.delete(id)
      }
      return next
    })

  const toggleMany = (ids: string[], select: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev)
      for (const id of ids) {
        if (select) next.add(id)
        else next.delete(id)
      }
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
      showToast(
        "An error occurred.",
        "Could not delete the selection.",
        "error",
      )
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })

  const act = useMutation({
    mutationFn: async ({
      ids,
      action,
    }: { ids: string[]; action: RowAction }) => {
      if (action === "rebuild") {
        await finalizePipelineBatch(ids[0])
        return
      }
      for (const id of ids) {
        try {
          if (action === "delete") await deletePipeline(id)
          else await processPipelineTask(id, action)
        } catch {
          // not applicable to this row
        }
      }
    },
    onSuccess: (_d, { action }) => {
      if (action === "rebuild")
        showToast("Rebuilding", "Combined tileset is being rebuilt.", "success")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
  const onAction = (ids: string[], action: RowAction) =>
    act.mutate({ ids, action })

  const batchAct = useMutation({
    mutationFn: async ({
      batchId,
      action,
    }: { batchId: string; action: BatchAction }) => {
      if (action === "rebuild") return finalizePipelineBatch(batchId)
      // server-side, so unloaded members are included
      return processPipelineBatchTask(batchId, action)
    },
    onSuccess: (_d, { action }) => {
      if (action === "rebuild")
        showToast("Rebuilding", "Combined tileset is being rebuilt.", "success")
    },
    onError: () => {
      showToast(
        "An error occurred.",
        "Could not apply the batch action.",
        "error",
      )
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
  const onBatchAction = (batchId: string, action: BatchAction) =>
    batchAct.mutate({ batchId, action })

  const editPipeline = (p: PipelinePublic) =>
    setEditTarget({
      kind: "single",
      id: p.id,
      label: p.title,
      type: pipelineType(p),
      sampleKey: p.source?.key ?? undefined,
      input: p.source?.key ?? undefined,
      values: formValuesFromConfig(pipelineType(p), p.data),
    })
  const editBatch = (summary: PipelineBatchSummary) =>
    setEditTarget({
      kind: "batch",
      batchId: summary.batch_id,
      label: summary.label,
      type: summary.pipeline || "PointCloud",
      sampleKey: summary.sample_key || undefined,
      input: summary.prefix,
      values: formValuesFromConfig(
        summary.pipeline || "PointCloud",
        summary.data,
      ),
    })

  const bulkAction = useMutation({
    mutationFn: async (actionType: "run" | "cancel") => {
      for (const id of Array.from(selected)) {
        try {
          await processPipelineTask(id, actionType)
        } catch {
          // not applicable to this row
        }
      }
    },
    onSuccess: (_d, actionType) => {
      showToast(
        actionType === "run" ? "Started" : "Cancelled",
        `${selected.size} job(s).`,
        "success",
      )
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
          <Button
            size="sm"
            onClick={() => setPage(page - 1)}
            isDisabled={!hasPreviousPage}
          >
            Previous
          </Button>
          <span>Page {page}</span>
          <Button
            size="sm"
            isDisabled={!hasNextPage}
            onClick={() => setPage(page + 1)}
          >
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
            isLoading={
              bulkAction.isPending && bulkAction.variables === "cancel"
            }
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
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </Button>
        </Flex>
      )}

      <PipelineModal
        isOpen={!!editTarget}
        onClose={() => setEditTarget(null)}
        label={editTarget?.label}
        pipelineType={editTarget?.type}
        editSampleKey={editTarget?.sampleKey}
        editInput={editTarget?.input}
        initialValues={editTarget?.values}
        editPipelineId={
          editTarget?.kind === "single" ? editTarget.id : undefined
        }
        editBatchId={
          editTarget?.kind === "batch" ? editTarget.batchId : undefined
        }
      />
    </>
  )
}
