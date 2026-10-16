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
  Button,
  Checkbox,
  Container,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  HStack,
  Heading,
  Icon,
  Input,
  InputGroup,
  InputLeftElement,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Progress,
  Select,
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
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"
import { FiDownload, FiEdit, FiSearch, FiTrash } from "react-icons/fi"
import { z } from "zod"
import { AssetsService, PipelinesService } from "../../client"
import type { ApiError, PipelineCreate } from "../../client"
import useCustomToast from "../../hooks/useCustomToast"
import { handleError } from "../../utils"
import { createPipelineBatch } from "../../api/pipelineBatch"

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
    await PipelinesService.deletePipeline({ id: id })
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
      <Button onClick={deleteModal.onOpen} color="ui.danger" variant="unstyled">
        <FiTrash fontSize="16px" />
      </Button>
      <DeleteDialog
        id={id}
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.onClose}
      />
    </>
  )
}

const PER_PAGE = 10

function getPipelinesQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      PipelinesService.readPipelines({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
      }),
    queryKey: ["pipelines", { page }],
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

function PipelinesTable() {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })

  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [query, setQuery] = React.useState("")

  const {
    data: pipelines,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getPipelinesQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
    refetchInterval: (options) => {
      const newPipelines = options?.state?.data || { data: [] }
      return newPipelines.data.find((pipeline) =>
        isCeleryTaskInProgress(pipeline.task_status),
      )
        ? 1000
        : false
    },
  })

  const rows = (pipelines?.data || []).filter((p) =>
    p.title.toLowerCase().includes(query.toLowerCase()),
  )
  const hasNextPage = !isPlaceholderData && pipelines?.data.length === PER_PAGE
  const hasPreviousPage = page > 1
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id))

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getPipelinesQueryOptions({ page: page + 1 }))
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
      if (rows.every((r) => next.has(r.id))) rows.forEach((r) => next.delete(r.id))
      else rows.forEach((r) => next.add(r.id))
      return next
    })

  const bulkDelete = useMutation({
    mutationFn: async () => {
      for (const id of Array.from(selected)) {
        await PipelinesService.deletePipeline({ id })
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

      <TableContainer>
        <Table variant="simple">
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
              <Th>Status</Th>
              <Th />
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
              {rows.map((pipeline) => {
                const download = `${pipeline?.task_result?.download}`
                const source = (pipeline as any).source
                const subtitle = source?.key
                  ? `s3://…/${source.key}`
                  : pipeline.asset_id
                    ? "uploaded asset"
                    : "no input"
                return (
                  <Tr
                    key={pipeline.id}
                    opacity={isPlaceholderData ? 0.5 : 1}
                    bg={selected.has(pipeline.id) ? "blue.50" : undefined}
                    _dark={{
                      bg: selected.has(pipeline.id) ? "blue.900" : undefined,
                    }}
                  >
                    <Td>
                      <Checkbox
                        isChecked={selected.has(pipeline.id)}
                        onChange={() => toggle(pipeline.id)}
                        aria-label={`Select ${pipeline.title}`}
                      />
                    </Td>
                    <Td>
                      <Flex direction="column" gap={0.5} minW={0}>
                        {pipeline.asset_id ? (
                          <Link
                            to="/pipeline/$pipelineId"
                            params={{ pipelineId: pipeline.id }}
                          >
                            <HStack>
                              <FiEdit fontSize="14px" />
                              <Text fontWeight="600">{pipeline.title}</Text>
                            </HStack>
                          </Link>
                        ) : (
                          <Text fontWeight="600">{pipeline.title}</Text>
                        )}
                        <Text fontSize="xs" color="gray.500">
                          {subtitle}
                        </Text>
                      </Flex>
                    </Td>
                    <Td>
                      <Flex gap={2} alignItems="center">
                        <StatusCell status={pipeline.task_status} />
                        {pipeline.task_result && (
                          <Tooltip label="Download 3D Tiles">
                            <a href={download} download={`${pipeline.title}.zip`}>
                              <FiDownload fontSize="16px" />
                            </a>
                          </Tooltip>
                        )}
                      </Flex>
                    </Td>
                    <Td maxWidth="60px">
                      <RemoveButton id={pipeline.id} />
                    </Td>
                  </Tr>
                )
              })}
            </Tbody>
          )}
        </Table>
      </TableContainer>

      <Flex gap={4} alignItems="center" mt={4} justifyContent="center">
        <Button onClick={() => setPage(page - 1)} isDisabled={!hasPreviousPage}>
          Previous
        </Button>
        <span>Page {page}</span>
        <Button isDisabled={!hasNextPage} onClick={() => setPage(page + 1)}>
          Next
        </Button>
      </Flex>

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
    </>
  )
}

const SelectAssets = React.forwardRef((props: any, ref) => {
  const { data: assets } = useQuery({
    queryFn: () =>
      AssetsService.readAssets({
        skip: 0,
        limit: 9999,
        extension: ".shp.zip,.las,.laz,.phg.zip,.obj,.obj.zip",
        uploadStatus: "SUCCESS",
      }),
    queryKey: ["assets-select"],
  })

  return (
    <Select {...props} ref={ref}>
      {assets?.data.map((asset) => {
        return (
          <option key={asset.id} value={asset.id}>
            {asset.filename}
          </option>
        )
      })}
    </Select>
  )
})

interface AddPipelineProps {
  isOpen: boolean
  onClose: () => void
}

const AddPipeline = ({ isOpen, onClose }: AddPipelineProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PipelineCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      title: "",
      data: {},
      task_id: null,
      task_status: null,
      task_result: null,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: PipelineCreate) => {
      return PipelinesService.createPipeline({ requestBody: data })
    },

    onSuccess: () => {
      showToast("Success!", "Pipeline created successfully.", "success")
      reset()
      onClose()
    },
    onError: (err: ApiError) => {
      handleError(err, showToast)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })

  const onSubmit: SubmitHandler<PipelineCreate> = (data) => {
    mutation.mutate(data)
  }

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        size={{ base: "sm", md: "md" }}
        isCentered
      >
        <ModalOverlay />
        <ModalContent as="form" onSubmit={handleSubmit(onSubmit)}>
          <ModalHeader>Add Pipeline</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <FormControl isRequired isInvalid={!!errors.asset_id}>
              <FormLabel htmlFor="asset">Asset</FormLabel>
              <SelectAssets
                id="asset_id"
                {...register("asset_id", {
                  required: "Asset is required."
                })}
                placeholder="Select asset"
              />
              {errors.asset_id && (
                <FormErrorMessage>{errors.asset_id.message}</FormErrorMessage>
              )}
            </FormControl>
            <FormControl isRequired isInvalid={!!errors.title}>
              <FormLabel htmlFor="title">Title</FormLabel>
              <Input
                id="title"
                {...register("title", {
                  required: "Title is required.",
                })}
                placeholder="Title"
                type="text"
              />
              {errors.title && (
                <FormErrorMessage>{errors.title.message}</FormErrorMessage>
              )}
            </FormControl>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button variant="primary" type="submit" isLoading={isSubmitting}>
              Save
            </Button>
            <Button onClick={onClose}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

interface NewBatchProps {
  isOpen: boolean
  onClose: () => void
}

interface BatchFormValues {
  prefix: string
  title?: string
  sample_radius?: string
  to_ellipsoidal_height?: boolean
}

const NewBatch = ({ isOpen, onClose }: NewBatchProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<BatchFormValues>({
    mode: "onBlur",
    defaultValues: {
      prefix: "",
      title: "",
      sample_radius: "",
      to_ellipsoidal_height: false,
    },
  })

  const mutation = useMutation({
    mutationFn: (values: BatchFormValues) => {
      const data: Record<string, unknown> = {}
      if (values.sample_radius) data.sample_radius = Number(values.sample_radius)
      if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
      return createPipelineBatch({
        prefix: values.prefix,
        pipeline: "PointCloud",
        title: values.title || null,
        data,
      })
    },
    onSuccess: (res) => {
      showToast("Success!", `Queued ${res.count} point-cloud jobs.`, "success")
      reset()
      onClose()
    },
    onError: () => {
      showToast("An error occurred.", "Could not create the batch.", "error")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })

  const onSubmit: SubmitHandler<BatchFormValues> = (values) => {
    mutation.mutate(values)
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={{ base: "sm", md: "md" }}
      isCentered
    >
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit(onSubmit)}>
        <ModalHeader>New point-cloud batch</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6} display="flex" flexDirection="column" gap={4}>
          <FormControl isRequired isInvalid={!!errors.prefix}>
            <FormLabel htmlFor="prefix">Bucket prefix</FormLabel>
            <Input
              id="prefix"
              placeholder="e.g. city-timisoara/"
              {...register("prefix", { required: "Prefix is required." })}
            />
            {errors.prefix && (
              <FormErrorMessage>{errors.prefix.message}</FormErrorMessage>
            )}
          </FormControl>
          <FormControl>
            <FormLabel htmlFor="title">Batch title (optional)</FormLabel>
            <Input id="title" placeholder="Title" {...register("title")} />
          </FormControl>
          <FormControl>
            <FormLabel htmlFor="sample_radius">Sample radius (m, optional)</FormLabel>
            <Input
              id="sample_radius"
              type="number"
              step="0.01"
              placeholder="e.g. 0.05"
              {...register("sample_radius")}
            />
          </FormControl>
          <FormControl>
            <Checkbox {...register("to_ellipsoidal_height")}>
              Convert to ellipsoidal height
            </Checkbox>
          </FormControl>
        </ModalBody>
        <ModalFooter gap={3}>
          <Button variant="primary" type="submit" isLoading={isSubmitting}>
            Create jobs
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

function Pipelines() {
  const addModal = useDisclosure()
  const batchModal = useDisclosure()
  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} pt={12}>
        Pipelines
      </Heading>
      <Flex py={8} gap={4}>
        <Button gap={1} onClick={addModal.onOpen} variant="outline" size="sm">
          <Icon as={FaPlus} /> Add Pipeline
        </Button>
        <Button gap={1} onClick={batchModal.onOpen} variant="primary" size="sm">
          <Icon as={FaPlus} /> New batch
        </Button>
        <AddPipeline isOpen={addModal.isOpen} onClose={addModal.onClose} />
        <NewBatch isOpen={batchModal.isOpen} onClose={batchModal.onClose} />
      </Flex>
      <PipelinesTable />
    </Container>
  )
}
