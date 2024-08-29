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
  FormLabel,
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
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import React from "react"
import { useEffect } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"
import { FiTrash } from "react-icons/fi"
import { z } from "zod"
import { AssetsService } from "../../client"
import type { ApiError } from "../../client"
import useCustomToast from "../../hooks/useCustomToast"
import { handleError } from "../../utils"

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
    await AssetsService.deleteAsset({ id: id })
  }

  const mutation = useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => {
      showToast("Success", "The Asset was deleted successfully.", "success")
      onClose()
    },
    onError: () => {
      showToast(
        "An error occurred.",
        "An error occurred while deleting the Asset.",
        "error",
      )
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["assets"],
      })
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
            <AlertDialogHeader>Delete Asset</AlertDialogHeader>

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

const assetsSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/assets")({
  component: Assets,
  validateSearch: (search) => assetsSearchSchema.parse(search),
})

const PER_PAGE = 10

function getAssetsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      AssetsService.readAssets({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
      }),
    queryKey: ["assets", { page }],
  }
}

function AssetsTable() {
  const queryClient = useQueryClient()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })

  const {
    data: assets,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getAssetsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
    refetchInterval: (options) => {
      const newAssets = options?.state?.data || { data: [] }
      return newAssets.data.find((asset) => asset.upload_status === "PENDING")
        ? 1000
        : false
    },
  })

  const hasNextPage = !isPlaceholderData && assets?.data.length === PER_PAGE
  const hasPreviousPage = page > 1

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getAssetsQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  return (
    <>
      <TableContainer>
        <Table>
          <Thead>
            <Tr>
              <Th>Filename</Th>
              <Th>Extension</Th>
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
              {assets?.data.map((asset) => (
                <Tr key={asset.id} opacity={isPlaceholderData ? 0.5 : 1}>
                  <Td>{asset.filename}</Td>
                  <Td>{asset.extension}</Td>
                  <Td>
                    <Flex gap={2}>
                      <Badge
                        colorScheme={
                          asset.upload_status === "PENDING"
                            ? "yellow"
                            : asset.upload_status === "SUCCESS"
                              ? "green"
                              : "red"
                        }
                      >
                        {asset.upload_status}
                      </Badge>
                    </Flex>
                  </Td>
                  <Td>
                    <RemoveButton id={asset.id} />
                  </Td>
                </Tr>
              ))}
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

interface AddAssetProps {
  isOpen: boolean
  onClose: () => void
}

const AddAsset = ({ isOpen, onClose }: AddAssetProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<any>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {},
  })

  const mutation = useMutation({
    mutationFn: (data: any) => {
      return AssetsService.createAsset({ formData: { file: data.file[0] } })
    },

    onSuccess: () => {
      showToast("Success!", "Asset created successfully.", "success")
      reset()
      onClose()
    },
    onError: (err: ApiError) => {
      handleError(err, showToast)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
    },
  })

  const onSubmit: SubmitHandler<any> = (data) => {
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
          <ModalHeader>Add Asset</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <FormControl isRequired isInvalid={!!errors.file}>
              <FormLabel htmlFor="title">File</FormLabel>
              <Input
                id="file"
                {...register("file", {
                  required: "File is required.",
                })}
                disabled={mutation.isPending}
                placeholder="File"
                name="file"
                type="file"
                p={0}
                sx={{
                  "::file-selector-button": {
                    height: 10,
                    padding: 0,
                    mr: 2,
                    pr: 2,
                    pl: 2,
                    border: "none",
                    fontWeight: "normal",
                    cursor: "pointer",
                  },
                }}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              variant="primary"
              type="submit"
              isLoading={isSubmitting || mutation.isPending}
            >
              Save
            </Button>
            <Button onClick={onClose}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

function Assets() {
  const addModal = useDisclosure()
  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} pt={12}>
        Assets
      </Heading>
      <Flex py={8} gap={4}>
        <Button gap={1} onClick={addModal.onOpen} variant="outline" size="sm">
          <Icon as={FaPlus} /> Add Asset
        </Button>
        <AddAsset isOpen={addModal.isOpen} onClose={addModal.onClose} />
      </Flex>
      <AssetsTable />
    </Container>
  )
}
