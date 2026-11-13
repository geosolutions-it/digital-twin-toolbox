import {
  Button,
  FormControl,
  FormLabel,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import React from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { uploadToStorage } from "../../api/storageBrowser"
import useCustomToast from "../../hooks/useCustomToast"

interface UploadProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix: string
}

interface UploadFormValues {
  prefix: string
  file: FileList
}

const UploadModal = ({ isOpen, onClose, initialPrefix }: UploadProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UploadFormValues>({ mode: "onBlur" })

  React.useEffect(() => {
    if (isOpen) reset({ prefix: initialPrefix })
  }, [isOpen, initialPrefix, reset])

  const mutation = useMutation({
    mutationFn: (data: UploadFormValues) =>
      uploadToStorage(data.file[0], data.prefix || ""),
    onSuccess: (res) => {
      showToast("Uploaded", res.key, "success")
      reset()
      onClose()
    },
    onError: () => {
      showToast("An error occurred.", "Could not upload the file.", "error")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["storage"] })
    },
  })

  const onSubmit: SubmitHandler<UploadFormValues> = (data) =>
    mutation.mutate(data)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={{ base: "sm", md: "md" }}
      isCentered
    >
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit(onSubmit)}>
        <ModalHeader>Upload to bucket</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6} display="flex" flexDirection="column" gap={4}>
          <FormControl>
            <FormLabel htmlFor="prefix">Destination folder</FormLabel>
            <Input
              id="prefix"
              placeholder="e.g. city-timisoara/"
              {...register("prefix")}
            />
          </FormControl>
          <FormControl isRequired isInvalid={!!errors.file}>
            <FormLabel htmlFor="file">File</FormLabel>
            <Input
              id="file"
              {...register("file", { required: "File is required." })}
              disabled={mutation.isPending}
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
            Upload
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

export default UploadModal
