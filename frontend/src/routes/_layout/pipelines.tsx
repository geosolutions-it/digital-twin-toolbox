import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Badge,
  Button,
  Container,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  HStack,
  Heading,
  Icon,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Select,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
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
import { FiDownload, FiEdit, FiFileMinus, FiTrash } from "react-icons/fi"
import { z } from "zod"
import { AssetsService, PipelinesService } from "../../client"
import type { ApiError, PipelineCreate } from "../../client"
import { OpenAPI } from "../../client/core/OpenAPI"
import useCustomToast from "../../hooks/useCustomToast"
import { handleError } from "../../utils"

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

function PipelinesTable() {
  const queryClient = useQueryClient()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })

  const {
    data: pipelines,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getPipelinesQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
    refetchInterval: (options) => {
      const newPipelines = options?.state?.data || { data: [] }
      return newPipelines.data.find(
        (pipeline) => pipeline.task_status === "PENDING",
      )
        ? 1000
        : false
    },
  })

  const hasNextPage = !isPlaceholderData && pipelines?.data.length === PER_PAGE
  const hasPreviousPage = page > 1

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getPipelinesQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  return (
    <>
      <TableContainer>
        <Table>
          <Thead>
            <Tr>
              <Th>Title</Th>
              <Th>Status</Th>
              <Th />
            </Tr>
          </Thead>
          {isPending ? (
            <Tbody>
              <Tr>
                {new Array(3).fill(null).map((_, index) => (
                  <Td key={index}>
                    <SkeletonText noOfLines={1} paddingBlock="16px" />
                  </Td>
                ))}
              </Tr>
            </Tbody>
          ) : (
            <Tbody>
              {pipelines?.data.map((pipeline) => {
                const download: string = `${OpenAPI.BASE}${pipeline?.task_result?.download}`
                return (
                  <Tr key={pipeline.id} opacity={isPlaceholderData ? 0.5 : 1}>
                    <Td>
                      {pipeline?.asset_id ? (
                        <Tooltip label="Click to edit pipeline">
                          <Link
                            to="/pipeline/$pipelineId"
                            params={{ pipelineId: pipeline.id }}
                          >
                            <HStack>
                              <FiEdit fontSize="16px" />
                              <span>{pipeline.title}</span>
                            </HStack>
                          </Link>
                        </Tooltip>
                      ) : (
                        <Tooltip label="The connected asset has been removed">
                          <Flex gap={2} alignItems="center">
                            <Icon
                              as={FiFileMinus}
                              color="ui.danger"
                              fontSize="16px"
                            />{" "}
                            {pipeline.title}
                          </Flex>
                        </Tooltip>
                      )}
                    </Td>
                    <Td>
                      <Flex gap={2} alignItems="center">
                        <Badge
                          colorScheme={
                            pipeline.task_status === "PENDING"
                              ? "yellow"
                              : pipeline.task_status === "SUCCESS"
                                ? "green"
                                : !pipeline.task_status
                                  ? "blue"
                                  : "red"
                          }
                        >
                          {pipeline.task_status || "READY"}
                        </Badge>
                        {pipeline.task_result && (
                          <Tooltip label="Download 3D Tiles">
                            <a
                              href={download}
                              download={`${pipeline.title}.zip`}
                            >
                              <FiDownload fontSize="16px" />
                            </a>
                          </Tooltip>
                        )}
                      </Flex>
                    </Td>
                    <Td maxWidth="80px">
                      <RemoveButton id={pipeline.id} />
                    </Td>
                  </Tr>
                )
              })}
            </Tbody>
          )}
        </Table>
      </TableContainer>
      <Flex
        gap={4}
        alignItems="center"
        mt={4}
        direction="row"
        justifyContent="center"
      >
        <Button onClick={() => setPage(page - 1)} isDisabled={!hasPreviousPage}>
          Previous
        </Button>
        <span>Page {page}</span>
        <Button isDisabled={!hasNextPage} onClick={() => setPage(page + 1)}>
          Next
        </Button>
      </Flex>
    </>
  )
}

const SelectAssets = React.forwardRef((props: any, ref) => {
  const { data: assets } = useQuery({
    queryFn: () =>
      AssetsService.readAssets({
        skip: 0,
        limit: 9999,
        extension: ".shp.zip,.las,.laz",
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
            <FormControl isRequired isInvalid={!!errors.asset_id}>
              <FormLabel htmlFor="asset">Asset</FormLabel>
              <SelectAssets
                id="asset_id"
                {...register("asset_id", {
                  required: "Asset is required.",
                })}
                placeholder="Select asset"
              />
              {errors.asset_id && (
                <FormErrorMessage>{errors.asset_id.message}</FormErrorMessage>
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

function Pipelines() {
  const addModal = useDisclosure()
  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} pt={12}>
        Pipelines
      </Heading>
      <Flex py={8} gap={4}>
        <Button gap={1} onClick={addModal.onOpen} variant="outline" size="sm">
          <Icon as={FaPlus} /> Add Pipeline
        </Button>
        <AddPipeline isOpen={addModal.isOpen} onClose={addModal.onClose} />
      </Flex>
      <PipelinesTable />
    </Container>
  )
}
