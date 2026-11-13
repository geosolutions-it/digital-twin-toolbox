import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
  IconButton,
  Tooltip,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import React from "react"
import { useForm } from "react-hook-form"
import { FiTrash } from "react-icons/fi"
import { deletePipeline } from "../../api"
import { deletePipelineBatch } from "../../api/pipelineBatch"
import useCustomToast from "../../hooks/useCustomToast"

interface DeleteProps {
  id: string
  batch?: boolean
  isOpen: boolean
  onClose: () => void
}

const DeleteDialog = ({ id, batch, isOpen, onClose }: DeleteProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const cancelRef = React.useRef<HTMLButtonElement | null>(null)
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm()

  const what = batch ? "Batch" : "Pipeline"
  const deleteEntity = async (id: string) => {
    if (batch) await deletePipelineBatch(id)
    else await deletePipeline(id)
  }

  const mutation = useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => {
      showToast("Success", `The ${what} was deleted successfully.`, "success")
      onClose()
    },
    onError: () => {
      showToast(
        "An error occurred.",
        `An error occurred while deleting the ${what}.`,
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
            <AlertDialogHeader>Delete {what}</AlertDialogHeader>

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
  batch?: boolean
}

export const RemoveButton = ({ id, batch }: RemoveButtonProps) => {
  const deleteModal = useDisclosure()
  const label = batch ? "Delete batch" : "Delete"
  return (
    <>
      <Tooltip label={label}>
        <IconButton
          aria-label={label}
          icon={<FiTrash />}
          size="xs"
          variant="ghost"
          colorScheme="red"
          onClick={deleteModal.onOpen}
        />
      </Tooltip>
      <DeleteDialog
        id={id}
        batch={batch}
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.onClose}
      />
    </>
  )
}
