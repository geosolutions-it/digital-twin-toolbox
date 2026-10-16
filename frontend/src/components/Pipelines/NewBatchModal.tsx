import {
  Button,
  Checkbox,
  FormControl,
  FormErrorMessage,
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
import { useEffect } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { createPipelineBatch } from "../../api/pipelineBatch"
import useCustomToast from "../../hooks/useCustomToast"

interface NewBatchModalProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix?: string
}

interface BatchFormValues {
  prefix: string
  title?: string
  sample_radius?: string
  to_ellipsoidal_height?: boolean
}

const NewBatchModal = ({ isOpen, onClose, initialPrefix = "" }: NewBatchModalProps) => {
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
      prefix: initialPrefix,
      title: "",
      sample_radius: "",
      to_ellipsoidal_height: false,
    },
  })

  useEffect(() => {
    if (isOpen) {
      reset({
        prefix: initialPrefix,
        title: "",
        sample_radius: "",
        to_ellipsoidal_height: false,
      })
    }
  }, [isOpen, initialPrefix, reset])

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
    <Modal isOpen={isOpen} onClose={onClose} size={{ base: "sm", md: "md" }} isCentered>
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

export default NewBatchModal
