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
  Select,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import {
  createPipelineBatch,
  createPipelineSource,
  getVectorFields,
  updateBatchConfig,
  updatePipelineConfig,
} from "../../api/pipelineBatch"
import { processPipelineTask } from "../../api/pipelines"
import useCustomToast from "../../hooks/useCustomToast"
import InputExpression from "../Viewer/InputExpression"

type PipelineType = "PointCloud" | "Polygon" | "Terrain" | "Instance"

interface NewBatchModalProps {
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
  initialValues?: Partial<BatchFormValues>
  label?: string
}

interface BatchFormValues {
  prefix: string
  title?: string
  pipelineType?: PipelineType
  sample_radius?: string
  to_ellipsoidal_height?: boolean
  ground_classification?: boolean
  colorization_image?: string
  lower_limit_height?: any
  upper_limit_height?: any
  remove_bottom_surface?: boolean
  max_features_per_tile?: string
  max_geometric_error?: string
  max_error?: string
  max_zoom?: string
  vertex_normals?: boolean
  water_key?: string
  model?: any
  models_prefix?: string
  scale?: any
  rotation?: any
  translate_z?: any
}

function heightValue(v: any): number | any[] | undefined {
  if (v == null || v === "") return undefined
  if (Array.isArray(v)) return v
  const n = Number(v)
  return Number.isNaN(n) ? undefined : n
}

const EMPTY: BatchFormValues = {
  prefix: "",
  title: "",
  pipelineType: "PointCloud",
  sample_radius: "",
  to_ellipsoidal_height: false,
  ground_classification: false,
  colorization_image: "",
  lower_limit_height: "",
  upper_limit_height: "",
  remove_bottom_surface: true,
  max_features_per_tile: "",
  max_geometric_error: "",
  max_error: "",
  max_zoom: "",
  vertex_normals: true,
  water_key: "",
  model: "",
  models_prefix: "",
  scale: "",
  rotation: "",
  translate_z: "",
}

function buildData(values: BatchFormValues, type: PipelineType): Record<string, unknown> {
  const data: Record<string, unknown> = {}
  if (type === "Terrain") {
    if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (values.max_zoom) data.max_zoom = Number(values.max_zoom)
    data.vertex_normals = !!values.vertex_normals
    if (values.water_key) data.water_key = values.water_key
    return data
  }
  if (type === "Instance") {
    if (values.model) data.model = values.model
    if (values.models_prefix) data.models_prefix = values.models_prefix
    const scale = heightValue(values.scale)
    const rotation = heightValue(values.rotation)
    const tz = heightValue(values.translate_z)
    if (scale !== undefined) data.scale = scale
    if (rotation !== undefined) data.rotation = rotation
    if (tz !== undefined) data.translate_z = tz
    if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (values.max_features_per_tile) data.max_features_per_tile = Number(values.max_features_per_tile)
    if (values.max_geometric_error) data.max_geometric_error = Number(values.max_geometric_error)
    return data
  }
  if (type === "Polygon") {
    const upper = heightValue(values.upper_limit_height)
    const lower = heightValue(values.lower_limit_height)
    if (upper !== undefined) data.upper_limit_height = upper
    if (lower !== undefined) data.lower_limit_height = lower
    if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    data.remove_bottom_surface = !!values.remove_bottom_surface
    if (values.max_features_per_tile) data.max_features_per_tile = Number(values.max_features_per_tile)
    if (values.max_geometric_error) data.max_geometric_error = Number(values.max_geometric_error)
    return data
  }
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
  pipelineType,
  selectableType,
  editPipelineId,
  editBatchId,
  editSampleKey,
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
    watch,
    control,
    formState: { errors, isSubmitting },
  } = useForm<BatchFormValues>({
    mode: "onBlur",
    defaultValues: { ...EMPTY, prefix: initialPrefix },
  })

  useEffect(() => {
    if (!isOpen) return
    reset(
      edit
        ? { ...EMPTY, pipelineType, ...initialValues }
        : { ...EMPTY, prefix: initialPrefix, pipelineType: pipelineType ?? "PointCloud" },
    )
  }, [isOpen, initialPrefix, initialValues, pipelineType, edit, reset])

  const watchedType = watch("pipelineType")
  const baseType: PipelineType = pipelineType ?? watchedType ?? "PointCloud"

  const fieldsParam: { key?: string; prefix?: string } | null = fileKey
    ? { key: fileKey }
    : editSampleKey
      ? { key: editSampleKey }
      : !edit
        ? { prefix: initialPrefix }
        : null
  const vectorLike = baseType === "Polygon" || baseType === "Instance"
  const { data: vectorFields } = useQuery({
    queryKey: ["vector-fields", fieldsParam],
    queryFn: () => getVectorFields(fieldsParam!),
    enabled: isOpen && vectorLike && !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
  })
  const properties = vectorFields?.properties ?? {}
  // a point layer can only be instanced, never extruded; upgrade Polygon -> Instance
  const type: PipelineType =
    baseType === "Polygon" && (vectorFields as any)?.geometry_type === "Point" ? "Instance" : baseType

  const mutation = useMutation({
    mutationFn: async ({ values, run }: { values: BatchFormValues; run: boolean }) => {
      const data = buildData(values, type)
      if (edit) {
        if (editBatchId) await updateBatchConfig(editBatchId, data)
        else await updatePipelineConfig(editPipelineId!, data)
        if (run) {
          const ids = targetIds && targetIds.length ? targetIds : editPipelineId ? [editPipelineId] : []
          for (const id of ids) {
            try {
              await processPipelineTask(id, "run")
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
    (run: boolean): SubmitHandler<BatchFormValues> =>
    (values) =>
      mutation.mutate({ values, run })

  const heading = edit
    ? `Adjust parameters${label ? `: ${label}` : ""}`
    : single
      ? "Process file"
      : "New batch"

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
          {!edit && selectableType && (
            <FormControl>
              <FormLabel htmlFor="pipelineType">Workflow</FormLabel>
              <Select id="pipelineType" {...register("pipelineType")}>
                <option value="PointCloud">Point cloud</option>
                <option value="Polygon">Polygon</option>
                <option value="Instance">Point instance</option>
                <option value="Terrain">Terrain</option>
              </Select>
            </FormControl>
          )}
          {!edit && (
            <FormControl>
              <FormLabel htmlFor="title">Title (optional)</FormLabel>
              <Input id="title" placeholder="Title" {...register("title")} />
            </FormControl>
          )}

          {type === "Instance" ? (
            <>
              <Text fontSize="xs" color="gray.500">
                Point layer: each point places a glb model, instanced in 3D Tiles.
              </Text>
              <FormControl>
                <FormLabel>Model (bucket key or attribute)</FormLabel>
                <Controller
                  control={control}
                  name="model"
                  render={({ field }) => (
                    <InputExpression id="model" type="string" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="models_prefix">Models prefix (optional)</FormLabel>
                <Input id="models_prefix" placeholder="e.g. models/" fontFamily="mono" fontSize="sm" {...register("models_prefix")} />
              </FormControl>
              <FormControl>
                <FormLabel>Scale (optional)</FormLabel>
                <Controller
                  control={control}
                  name="scale"
                  render={({ field }) => (
                    <InputExpression id="scale" type="number" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <FormControl>
                <FormLabel>Rotation (deg, optional)</FormLabel>
                <Controller
                  control={control}
                  name="rotation"
                  render={({ field }) => (
                    <InputExpression id="rotation" type="number" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <FormControl>
                <FormLabel>Height offset (m, optional)</FormLabel>
                <Controller
                  control={control}
                  name="translate_z"
                  render={({ field }) => (
                    <InputExpression id="translate_z" type="number" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <FormControl>
                <Checkbox {...register("to_ellipsoidal_height")}>
                  Convert heights to ellipsoidal (EGM2008)
                </Checkbox>
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="max_features_per_tile">Max instances per tile (optional)</FormLabel>
                <Input id="max_features_per_tile" type="number" placeholder="25000" {...register("max_features_per_tile")} />
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="max_geometric_error">Max geometric error (optional)</FormLabel>
                <Input id="max_geometric_error" type="number" placeholder="500" {...register("max_geometric_error")} />
              </FormControl>
            </>
          ) : type === "Terrain" ? (
            <>
              <FormControl>
                <FormLabel htmlFor="max_zoom">Max zoom (optional)</FormLabel>
                <Input id="max_zoom" type="number" placeholder="auto from resolution" {...register("max_zoom")} />
              </FormControl>
              <FormControl>
                <Checkbox {...register("to_ellipsoidal_height")}>
                  Convert heights to ellipsoidal (EGM2008)
                </Checkbox>
              </FormControl>
              <FormControl>
                <Checkbox {...register("vertex_normals")}>Vertex normals (lighting)</Checkbox>
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="water_key">Water layer (bucket key, optional)</FormLabel>
                <Input id="water_key" placeholder="e.g. water/coastline.gpkg" fontFamily="mono" fontSize="sm" {...register("water_key")} />
              </FormControl>
            </>
          ) : type === "Polygon" ? (
            <>
              <FormControl>
                <FormLabel>Building height (m, optional)</FormLabel>
                <Controller
                  control={control}
                  name="upper_limit_height"
                  render={({ field }) => (
                    <InputExpression id="upper_limit_height" type="number" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <FormControl>
                <FormLabel>Base height (m, optional)</FormLabel>
                <Controller
                  control={control}
                  name="lower_limit_height"
                  render={({ field }) => (
                    <InputExpression id="lower_limit_height" type="number" properties={properties} value={field.value} onChange={field.onChange} />
                  )}
                />
              </FormControl>
              <Text fontSize="xs" color="gray.500">
                Use the menu on a field to bind a value to an attribute (e.g. height from a column).
              </Text>
              <FormControl>
                <Checkbox {...register("to_ellipsoidal_height")}>
                  Convert heights to ellipsoidal (EGM2008)
                </Checkbox>
              </FormControl>
              <FormControl>
                <Checkbox {...register("remove_bottom_surface")}>Remove bottom surface</Checkbox>
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="max_features_per_tile">Max features per tile (optional)</FormLabel>
                <Input id="max_features_per_tile" type="number" placeholder="1000" {...register("max_features_per_tile")} />
              </FormControl>
              <FormControl>
                <FormLabel htmlFor="max_geometric_error">Max geometric error (optional)</FormLabel>
                <Input id="max_geometric_error" type="number" placeholder="500" {...register("max_geometric_error")} />
              </FormControl>
            </>
          ) : (
            <>
              <FormControl>
                <FormLabel htmlFor="sample_radius">Sample radius (m, empty = auto)</FormLabel>
                <Input
                  id="sample_radius"
                  type="number"
                  step="0.01"
                  placeholder="auto"
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
            </>
          )}
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
export type { BatchFormValues, PipelineType }
