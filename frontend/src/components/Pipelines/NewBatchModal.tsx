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
import {
  createPipelineBatch,
  createPipelineSource,
  updateBatchConfig,
  updatePipelineConfig,
} from "../../api/pipelineBatch"
import { PipelinesService } from "../../client"
import useCustomToast from "../../hooks/useCustomToast"

interface NewBatchModalProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix?: string
  fileKey?: string
  editPipelineId?: string
  editBatchId?: string
  targetIds?: string[]
  initialValues?: Partial<BatchFormValues>
  label?: string
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

function buildData(values: BatchFormValues): Record<string, unknown> {
  const data: Record<string, unknown> = {}
  if (values.sample_radius) data.sample_radius = Number(values.sample_radius)
  if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
  if (values.ground_classification) data.ground_classification = true
  if (values.colorization_image) data.colorization_image = values.colorization_image
  return data
}

const NewBatchModal = ({
  isOpen,
  onClose,
  initialPrefix = "",
  fileKey,
  editPipelineId,
  editBatchId,
  targetIds,
  initialValues,
  label,
}: NewBatchModalProps) => {
  const single = !!fileKey
  const edit = !!editPipelineId || !!editBatchId
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
    if (!isOpen) return
    reset(edit ? { ...EMPTY, ...initialValues } : { ...EMPTY, prefix: initialPrefix })
  }, [isOpen, initialPrefix, initialValues, edit, reset])

  const mutation = useMutation({
    mutationFn: async ({ values, run }: { values: BatchFormValues; run: boolean }) => {
      const data = buildData(values)
      if (edit) {
        if (editBatchId) await updateBatchConfig(editBatchId, data)
        else await updatePipelineConfig(editPipelineId!, data)
        if (run) {
          const ids = targetIds && targetIds.length ? targetIds : editPipelineId ? [editPipelineId] : []
          for (const id of ids) {
            try {
              await PipelinesService.processPipelineTask({ id, actionType: "run" })
            } catch {
              // skip rows the run does not apply to (already running)
            }
          }
        }
        return { edited: true, run }
      }
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
      let msg: string
      if (edit) msg = res?.run ? "Saved and re-running." : "Parameters saved."
      else if (single) msg = "Queued 1 point-cloud job."
      else msg = `Queued ${res.count} point-cloud jobs.`
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

  const submit =
    (run: boolean): SubmitHandler<BatchFormValues> =>
    (values) =>
      mutation.mutate({ values, run })

  const heading = edit
    ? `Adjust parameters${label ? `: ${label}` : ""}`
    : single
      ? "Process point cloud"
      : "New point-cloud batch"

  return (
    <Modal isOpen={isOpen} onClose={onClose} size={{ base: "sm", md: "md" }} isCentered>
      <ModalOverlay />
      <ModalContent as="form" onSubmit={handleSubmit(submit(!edit))}>
        <ModalHeader>{heading}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6} display="flex" flexDirection="column" gap={4}>
          {!edit &&
            (single ? (
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
            ))}
          {!edit && (
            <FormControl>
              <FormLabel htmlFor="title">Title (optional)</FormLabel>
              <Input id="title" placeholder="Title" {...register("title")} />
            </FormControl>
          )}
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
          {edit ? (
            <>
              <Button
                type="button"
                variant="outline"
                isLoading={isSubmitting}
                onClick={handleSubmit(submit(false))}
              >
                Save
              </Button>
              <Button
                type="button"
                variant="primary"
                isLoading={isSubmitting}
                onClick={handleSubmit(submit(true))}
              >
                Save & run
              </Button>
            </>
          ) : (
            <Button variant="primary" type="submit" isLoading={isSubmitting}>
              {single ? "Process" : "Create jobs"}
            </Button>
          )}
          <Button type="button" onClick={onClose} variant="ghost">
            Cancel
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

export default NewBatchModal
export type { BatchFormValues }
