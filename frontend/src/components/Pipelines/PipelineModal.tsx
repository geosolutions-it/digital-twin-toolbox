import {
  Box,
  Button,
  Flex,
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
  Select,
  Spinner,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Suspense, lazy, useEffect } from "react"
import { FormProvider, type SubmitHandler, useForm } from "react-hook-form"
import {
  createPipelineBatch,
  createPipelineSource,
  getMeshBbox,
  getVectorFields,
  getVectorSample,
  processPipelineBatchTask,
  updateBatchConfig,
  updatePipelineConfig,
} from "../../api/pipelineBatch"
import { processPipelineTask } from "../../api/pipelines"
import type { PipelineType } from "../../api/types"
import useCustomToast from "../../hooks/useCustomToast"
import type { PreviewKind } from "./PreviewMap"
import {
  FORM_DEFAULTS,
  PIPELINE_FORMS,
  type PipelineFormValues,
  configFromValues,
} from "./forms"

const PreviewMap = lazy(() => import("./PreviewMap"))

const EMPTY: PipelineFormValues = {
  ...FORM_DEFAULTS,
  prefix: "",
  title: "",
  pipelineType: "PointCloud",
}

interface PipelineModalProps {
  isOpen: boolean
  onClose: () => void
  initialPrefix?: string
  fileKey?: string
  pipelineType?: PipelineType
  selectableType?: boolean
  editPipelineId?: string
  editBatchId?: string
  editSampleKey?: string
  targetIds?: string[]
  initialValues?: Partial<PipelineFormValues>
  label?: string
}

/** Creates a pipeline from one file or a batch from a folder, or edits an existing one. */
const PipelineModal = ({
  isOpen,
  onClose,
  initialPrefix = "",
  fileKey,
  pipelineType,
  selectableType,
  editPipelineId,
  editBatchId,
  editSampleKey,
  targetIds,
  initialValues,
  label,
}: PipelineModalProps) => {
  const single = !!fileKey
  const edit = !!editPipelineId || !!editBatchId
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const form = useForm<PipelineFormValues>({
    mode: "onBlur",
    defaultValues: { ...EMPTY, prefix: initialPrefix },
  })
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = form

  useEffect(() => {
    if (!isOpen) return
    reset(
      edit
        ? { ...EMPTY, pipelineType, ...initialValues }
        : {
            ...EMPTY,
            prefix: initialPrefix,
            pipelineType: pipelineType ?? "PointCloud",
          },
    )
  }, [isOpen, initialPrefix, initialValues, pipelineType, edit, reset])

  const watchedType = watch("pipelineType")
  const baseType: PipelineType =
    pipelineType === "Polygon" && watchedType === "Building"
      ? "Building"
      : pipelineType ?? watchedType ?? "PointCloud"

  const fieldsParam: { key?: string; prefix?: string } | null = fileKey
    ? { key: fileKey }
    : editSampleKey
      ? { key: editSampleKey }
      : !edit
        ? { prefix: initialPrefix }
        : null
  const vectorLike =
    baseType === "Polygon" || baseType === "Instance" || baseType === "Building"
  const ellipsoidal = !!watch("to_ellipsoidal_height")
  const { data: vectorFields } = useQuery({
    queryKey: ["vector-fields", fieldsParam],
    queryFn: () => getVectorFields(fieldsParam!),
    enabled:
      isOpen && vectorLike && !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
  })
  const sample = useQuery({
    queryKey: ["vector-sample", fieldsParam, ellipsoidal],
    queryFn: () => getVectorSample({ ...fieldsParam!, ellipsoidal }),
    enabled:
      isOpen && vectorLike && !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
  })
  const meshBbox = useQuery({
    queryKey: ["mesh-bbox", fieldsParam],
    queryFn: () => getMeshBbox(fieldsParam!),
    enabled:
      isOpen &&
      baseType === "Mesh" &&
      !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
    retry: false,
  })
  // point layers can only be instanced
  const type: PipelineType =
    baseType === "Polygon" && vectorFields?.geometry_type === "Point"
      ? "Instance"
      : baseType
  const { Fields } = PIPELINE_FORMS[type]

  const hasPreview =
    type === "Polygon" ||
    type === "Instance" ||
    type === "Mesh" ||
    type === "Building"
  const values = watch()
  const errorText = (e: any) =>
    e?.response?.data?.detail || e?.message || "unknown error"
  const previewStatus =
    type === "Mesh"
      ? meshBbox.isFetching
        ? "Reading the mesh size…"
        : meshBbox.error
          ? `No footprint: ${errorText(meshBbox.error)}`
          : undefined
      : sample.isFetching
        ? "Loading sample features…"
        : sample.error
          ? `No preview: ${errorText(sample.error)}`
          : undefined

  const mutation = useMutation({
    mutationFn: async ({
      values,
      run,
    }: { values: PipelineFormValues; run: boolean }) => {
      const data = configFromValues(type, values)
      if (edit) {
        if (editBatchId) await updateBatchConfig(editBatchId, data)
        else await updatePipelineConfig(editPipelineId!, data)
        if (run) {
          if (editBatchId) {
            // server-side, so unloaded members run too
            await processPipelineBatchTask(editBatchId, "run")
          } else {
            const ids = targetIds?.length
              ? targetIds
              : editPipelineId
                ? [editPipelineId]
                : []
            for (const id of ids) {
              try {
                await processPipelineTask(id, "run")
              } catch {
                // already running
              }
            }
          }
        }
        return { edited: true, run }
      }
      if (single) {
        return createPipelineSource({
          key: fileKey!,
          pipeline: type,
          title: values.title || null,
          data,
        })
      }
      return createPipelineBatch({
        prefix: values.prefix,
        pipeline: type,
        title: values.title || null,
        data,
      })
    },
    onSuccess: (res: any) => {
      let msg: string
      if (edit) msg = res?.run ? "Saved and re-running." : "Parameters saved."
      else if (single) msg = "Queued 1 job."
      else msg = `Queued ${res.count} jobs.`
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
    (run: boolean): SubmitHandler<PipelineFormValues> =>
    (values) => {
      if (!mutation.isPending) mutation.mutate({ values, run })
    }

  const heading = edit
    ? `Adjust parameters${label ? `: ${label}` : ""}`
    : single
      ? "Process file"
      : "New batch"

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={hasPreview ? { base: "full", lg: "6xl" } : { base: "sm", md: "md" }}
      isCentered
    >
      <ModalOverlay />
      <ModalContent
        as="form"
        onSubmit={handleSubmit(submit(!edit))}
        h={hasPreview ? { lg: "min(860px, calc(100vh - 7.5rem))" } : undefined}
      >
        <ModalHeader>{heading}</ModalHeader>
        <ModalCloseButton />
        <ModalBody
          pb={6}
          display="grid"
          gridTemplateColumns={
            hasPreview
              ? { base: "1fr", lg: "minmax(0, 380px) minmax(0, 1fr)" }
              : "1fr"
          }
          gridTemplateRows={hasPreview ? { lg: "minmax(0, 1fr)" } : undefined}
          minH={0}
          overflowY={hasPreview ? { base: "auto", lg: "hidden" } : undefined}
          gap={6}
        >
          <Flex
            direction="column"
            gap={4}
            minW={0}
            minH={0}
            overflowY={hasPreview ? { lg: "auto" } : undefined}
            pr={hasPreview ? 1 : 0}
            pt={1}
          >
            {!edit &&
              (single ? (
                <FormControl>
                  <FormLabel>File</FormLabel>
                  <Input
                    value={fileKey}
                    isReadOnly
                    fontFamily="mono"
                    fontSize="sm"
                  />
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
            {!edit && selectableType && (
              <FormControl>
                <FormLabel htmlFor="pipelineType">Workflow</FormLabel>
                <Select id="pipelineType" {...register("pipelineType")}>
                  <option value="PointCloud">Point cloud</option>
                  <option value="Polygon">Polygon</option>
                  <option value="Instance">Point instance</option>
                  <option value="Terrain">Terrain</option>
                  <option value="Mesh">Mesh (zipped obj)</option>
                  <option value="CityGML">
                    City model (CityGML, CityJSON)
                  </option>
                </Select>
              </FormControl>
            )}
            {!edit && single && pipelineType === "Polygon" && (
              <FormControl>
                <FormLabel htmlFor="pipelineType">Workflow</FormLabel>
                <Select id="pipelineType" {...register("pipelineType")}>
                  <option value="Polygon">Polygon (extrude)</option>
                  <option value="Building">
                    Buildings (roofs from a point cloud)
                  </option>
                </Select>
              </FormControl>
            )}
            {!edit && (
              <FormControl>
                <FormLabel htmlFor="title">Title (optional)</FormLabel>
                <Input id="title" placeholder="Title" {...register("title")} />
              </FormControl>
            )}

            <FormProvider {...form}>
              <Fields
                fieldNames={vectorFields?.fields?.map((f) => f.name)}
                sampleFeatures={sample.data?.features}
              />
            </FormProvider>
          </Flex>
          {hasPreview && (
            <Box h={{ base: "320px", lg: "100%" }} minW={0} minH={0}>
              <Suspense
                fallback={
                  <Flex
                    h="100%"
                    align="center"
                    justify="center"
                    bg="gray.900"
                    borderRadius="md"
                  >
                    <Spinner color="white" />
                  </Flex>
                }
              >
                <PreviewMap
                  kind={(type === "Building" ? "Polygon" : type) as PreviewKind}
                  values={
                    type === "Building"
                      ? {
                          ...values,
                          lower_limit_height: "",
                          upper_limit_height: "",
                        }
                      : values
                  }
                  features={sample.data?.features}
                  bbox={meshBbox.data}
                  status={previewStatus}
                  onPick={
                    type === "Mesh"
                      ? (lat, lon) => {
                          setValue("latitude", String(lat), {
                            shouldDirty: true,
                            shouldValidate: true,
                          })
                          setValue("longitude", String(lon), {
                            shouldDirty: true,
                            shouldValidate: true,
                          })
                        }
                      : undefined
                  }
                />
              </Suspense>
            </Box>
          )}
        </ModalBody>
        <ModalFooter gap={3}>
          {edit ? (
            <>
              <Button
                type="button"
                variant="outline"
                isLoading={mutation.isPending}
                onClick={handleSubmit(submit(false))}
              >
                Save
              </Button>
              <Button
                type="button"
                variant="primary"
                isLoading={mutation.isPending}
                onClick={handleSubmit(submit(true))}
              >
                Save & run
              </Button>
            </>
          ) : (
            <Button
              variant="primary"
              type="submit"
              isLoading={mutation.isPending}
            >
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

export default PipelineModal
