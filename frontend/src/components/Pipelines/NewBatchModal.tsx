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
import { createPipelineBatch, createPipelineSource } from "../../api/pipelineBatch"
import useCustomToast from "../../hooks/useCustomToast"

interface NewBatchModalProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix?: string
  fileKey?: string
}

interface BatchFormValues {
  prefix: string
  title?: string
  sample_radius?: string
  to_ellipsoidal_height?: boolean
  ground_classification?: boolean
  colorization_image?: string
}

const EMPTY: BatchFormValues = {
  prefix: "",
  title: "",
  sample_radius: "",
  to_ellipsoidal_height: false,
  ground_classification: false,
  colorization_image: "",
}

const NewBatchModal = ({ isOpen, onClose, initialPrefix = "", fileKey }: NewBatchModalProps) => {
  const single = !!fileKey
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<BatchFormValues>({
    mode: "onBlur",
    defaultValues: { ...EMPTY, prefix: initialPrefix },
  })

  useEffect(() => {
    if (isOpen) reset({ ...EMPTY, prefix: initialPrefix })
  }, [isOpen, initialPrefix, reset])

  const mutation = useMutation({
    mutationFn: (values: BatchFormValues) => {
      const data: Record<string, unknown> = {}
      if (values.sample_radius) data.sample_radius = Number(values.sample_radius)
      if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
      if (values.ground_classification) data.ground_classification = true
      if (values.colorization_image) data.colorization_image = values.colorization_image
      if (single) {
        return createPipelineSource({
          key: fileKey!,
          pipeline: "PointCloud",
          title: values.title || null,
          data,
        })
      }
      return createPipelineBatch({
        prefix: values.prefix,
        pipeline: "PointCloud",
        title: values.title || null,
        data,
      })
    },
    onSuccess: (res: any) => {
      const msg = single ? "Queued 1 point-cloud job." : `Queued ${res.count} point-cloud jobs.`
      showToast("Success!", msg, "success")
      reset()
      onClose()
    },
    onError: () => {
      showToast("An error occurred.", "Could not start the job.", "error")
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
        <ModalHeader>{single ? "Process point cloud" : "New point-cloud batch"}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6} display="flex" flexDirection="column" gap={4}>
          {single ? (
            <FormControl>
              <FormLabel>File</FormLabel>
              <Input value={fileKey} isReadOnly fontFamily="mono" fontSize="sm" />
            </FormControl>
          ) : (
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
          )}
          <FormControl>
            <FormLabel htmlFor="title">Title (optional)</FormLabel>
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
            <FormLabel htmlFor="colorization_image">Colorization raster (bucket key, optional)</FormLabel>
            <Input
              id="colorization_image"
              placeholder="e.g. rasters/orthophoto.tif"
              fontFamily="mono"
              fontSize="sm"
              {...register("colorization_image")}
            />
          </FormControl>
          <FormControl>
            <Checkbox {...register("to_ellipsoidal_height")}>
              Convert to ellipsoidal height
            </Checkbox>
          </FormControl>
          <FormControl>
            <Checkbox {...register("ground_classification")}>
              Classify ground points
            </Checkbox>
          </FormControl>
        </ModalBody>
        <ModalFooter gap={3}>
          <Button variant="primary" type="submit" isLoading={isSubmitting}>
            {single ? "Process" : "Create jobs"}
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

export default NewBatchModal
