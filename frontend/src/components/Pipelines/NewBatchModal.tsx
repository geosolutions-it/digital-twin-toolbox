import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormErrorMessage,
  Flex,
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
  Text,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Suspense, lazy, useEffect } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
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
import useCustomToast from "../../hooks/useCustomToast"
import ExpressionInput, { isInvalidExpression } from "./ExpressionInput"
import StorageKeyInput, { useStorageListing } from "./StorageKeyInput"
import type { PreviewKind } from "./PreviewMap"

const PreviewMap = lazy(() => import("./PreviewMap"))

type PipelineType = "PointCloud" | "Polygon" | "Terrain" | "Instance" | "Mesh"

// worker downloads water as a single file
const VECTOR_EXTENSIONS = [".gpkg", ".geojson", ".json", ".fgb"]
const RASTER_EXTENSIONS = [".tif", ".tiff", ".vrt", ".jp2"]

const AXES = [
  { value: "X", label: "X" },
  { value: "Y", label: "Y" },
  { value: "Z", label: "Z" },
  { value: "NEGATIVE_X", label: "-X" },
  { value: "NEGATIVE_Y", label: "-Y" },
  { value: "NEGATIVE_Z", label: "-Z" },
]

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
  max_tile_size_kb?: string
  max_zoom?: string
  vertex_normals?: boolean
  water_key?: string
  model?: any
  models_prefix?: string
  scale?: any
  rotation?: any
  translate_z?: any
  latitude?: string
  longitude?: string
  altitude?: string
  forward_axis?: string
  up_axis?: string
  depth?: string
  tile_faces_target?: string
  texture_image_size?: string
  decimate_last_depth_level?: boolean
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
  max_tile_size_kb: "",
  max_zoom: "",
  vertex_normals: true,
  water_key: "",
  model: "",
  models_prefix: "",
  scale: "",
  rotation: "",
  translate_z: "",
  latitude: "",
  longitude: "",
  altitude: "",
  forward_axis: "Y",
  up_axis: "Z",
  depth: "",
  tile_faces_target: "",
  texture_image_size: "",
  decimate_last_depth_level: true,
}

function buildData(
  values: BatchFormValues,
  type: PipelineType,
): Record<string, unknown> {
  const data: Record<string, unknown> = {}
  if (type === "Mesh") {
    data.latitude = Number(values.latitude || 0)
    data.longitude = Number(values.longitude || 0)
    data.altitude = Number(values.altitude || 0)
    data.forward_axis = values.forward_axis || "Y"
    data.up_axis = values.up_axis || "Z"
    if (values.depth) data.depth = Number(values.depth)
    if (values.tile_faces_target)
      data.tile_faces_target = Number(values.tile_faces_target)
    if (values.texture_image_size)
      data.texture_image_size = Number(values.texture_image_size)
    if (values.max_geometric_error)
      data.max_geometric_error = Number(values.max_geometric_error)
    data.decimate_last_depth_level = !!values.decimate_last_depth_level
    return data
  }
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
    if (values.max_features_per_tile)
      data.max_features_per_tile = Number(values.max_features_per_tile)
    if (values.max_geometric_error)
      data.max_geometric_error = Number(values.max_geometric_error)
    return data
  }
  if (type === "Polygon") {
    const upper = heightValue(values.upper_limit_height)
    const lower = heightValue(values.lower_limit_height)
    if (upper !== undefined) data.upper_limit_height = upper
    if (lower !== undefined) data.lower_limit_height = lower
    if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    data.remove_bottom_surface = !!values.remove_bottom_surface
    if (values.max_tile_size_kb)
      data.max_tile_size_kb = Number(values.max_tile_size_kb)
    return data
  }
  if (values.sample_radius) data.sample_radius = Number(values.sample_radius)
  if (values.to_ellipsoidal_height) data.to_ellipsoidal_height = true
  if (values.ground_classification) data.ground_classification = true
  if (values.colorization_image)
    data.colorization_image = values.colorization_image
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
    setValue,
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
        : {
            ...EMPTY,
            prefix: initialPrefix,
            pipelineType: pipelineType ?? "PointCloud",
          },
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
    enabled:
      isOpen && vectorLike && !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
  })
  const sample = useQuery({
    queryKey: ["vector-sample", fieldsParam],
    queryFn: () => getVectorSample(fieldsParam!),
    enabled:
      isOpen && vectorLike && !!(fieldsParam?.key || fieldsParam?.prefix),
    staleTime: 60000,
  })
  const vectorSample = sample.data
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
  const fieldNames = vectorFields?.fields?.map((f) => f.name)
  const sampleFeatures = sample.data?.features
  // point layers can only be instanced
  const type: PipelineType =
    baseType === "Polygon" && (vectorFields as any)?.geometry_type === "Point"
      ? "Instance"
      : baseType
  const modelsPrefix = watch("models_prefix") ?? ""
  const modelsDir = modelsPrefix.slice(0, modelsPrefix.lastIndexOf("/") + 1)
  const modelListing = useStorageListing(
    modelsDir,
    isOpen && type === "Instance",
  )
  // worker key is models_prefix + model
  const modelNames = modelListing.data?.files
    .filter(
      (f) =>
        f.key.startsWith(modelsPrefix) && f.key.toLowerCase().endsWith(".glb"),
    )
    .map((f) => f.key.slice(modelsPrefix.length))

  const hasPreview =
    type === "Polygon" || type === "Instance" || type === "Mesh"
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
    }: { values: BatchFormValues; run: boolean }) => {
      const data = buildData(values, type)
      if (edit) {
        if (editBatchId) await updateBatchConfig(editBatchId, data)
        else await updatePipelineConfig(editPipelineId!, data)
        if (run) {
          if (editBatchId) {
            // server-side, so unloaded members run too
            await processPipelineBatchTask(editBatchId, "run")
          } else {
            const ids =
              targetIds && targetIds.length
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
    (run: boolean): SubmitHandler<BatchFormValues> =>
    (values) =>
      mutation.mutate({ values, run })

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
                </Select>
              </FormControl>
            )}
            {!edit && (
              <FormControl>
                <FormLabel htmlFor="title">Title (optional)</FormLabel>
                <Input id="title" placeholder="Title" {...register("title")} />
              </FormControl>
            )}

            {type === "Mesh" ? (
              <>
                <Text fontSize="xs" color="gray.500">
                  The mesh origin (0, 0, 0) is placed at this location; vertices
                  are metres.
                </Text>
                <FormControl isRequired isInvalid={!!errors.latitude}>
                  <FormLabel htmlFor="latitude">Latitude</FormLabel>
                  <Input
                    id="latitude"
                    type="number"
                    step="any"
                    {...register("latitude", {
                      required: "Latitude is required.",
                    })}
                  />
                  {errors.latitude && (
                    <FormErrorMessage>
                      {errors.latitude.message}
                    </FormErrorMessage>
                  )}
                </FormControl>
                <FormControl isRequired isInvalid={!!errors.longitude}>
                  <FormLabel htmlFor="longitude">Longitude</FormLabel>
                  <Input
                    id="longitude"
                    type="number"
                    step="any"
                    {...register("longitude", {
                      required: "Longitude is required.",
                    })}
                  />
                  {errors.longitude && (
                    <FormErrorMessage>
                      {errors.longitude.message}
                    </FormErrorMessage>
                  )}
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="altitude">
                    Altitude (m, ellipsoidal)
                  </FormLabel>
                  <Input
                    id="altitude"
                    type="number"
                    step="any"
                    placeholder="0"
                    {...register("altitude")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="forward_axis">
                    Forward axis (north)
                  </FormLabel>
                  <Select id="forward_axis" {...register("forward_axis")}>
                    {AXES.map((a) => (
                      <option key={a.value} value={a.value}>
                        {a.label}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="up_axis">Up axis</FormLabel>
                  <Select id="up_axis" {...register("up_axis")}>
                    {AXES.map((a) => (
                      <option key={a.value} value={a.value}>
                        {a.label}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="depth">Depth (optional)</FormLabel>
                  <Input
                    id="depth"
                    type="number"
                    placeholder="4"
                    {...register("depth")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="tile_faces_target">
                    Faces per tile (optional)
                  </FormLabel>
                  <Input
                    id="tile_faces_target"
                    type="number"
                    placeholder="10000"
                    {...register("tile_faces_target")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="texture_image_size">
                    Texture size (px, optional)
                  </FormLabel>
                  <Input
                    id="texture_image_size"
                    type="number"
                    placeholder="512"
                    {...register("texture_image_size")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="max_geometric_error">
                    Max geometric error (optional)
                  </FormLabel>
                  <Input
                    id="max_geometric_error"
                    type="number"
                    placeholder="256"
                    {...register("max_geometric_error")}
                  />
                </FormControl>
                <FormControl>
                  <Checkbox {...register("decimate_last_depth_level")}>
                    Decimate the last level
                  </Checkbox>
                </FormControl>
              </>
            ) : type === "Instance" ? (
              <>
                <Text fontSize="xs" color="gray.500">
                  Point layer: each point places a glb model, instanced in 3D
                  Tiles.
                </Text>
                <FormControl>
                  <FormLabel htmlFor="models_prefix">
                    Models prefix (optional)
                  </FormLabel>
                  <Controller
                    control={control}
                    name="models_prefix"
                    render={({ field }) => (
                      <StorageKeyInput
                        id="models_prefix"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        placeholder="e.g. models/"
                        foldersOnly
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Model (bucket key or attribute)</FormLabel>
                  <Controller
                    control={control}
                    name="model"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="model"
                        type="string"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        literals={modelNames}
                        placeholder={'e.g. "tree.glb" or lower(type) + ".glb"'}
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Scale (optional)</FormLabel>
                  <Controller
                    control={control}
                    name="scale"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="scale"
                        type="number"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        placeholder="1"
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Rotation (deg, optional)</FormLabel>
                  <Controller
                    control={control}
                    name="rotation"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="rotation"
                        type="number"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        placeholder="0"
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Height offset (m, optional)</FormLabel>
                  <Controller
                    control={control}
                    name="translate_z"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="translate_z"
                        type="number"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        placeholder="0"
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <Checkbox {...register("to_ellipsoidal_height")}>
                    Convert heights to ellipsoidal (EGM2008)
                  </Checkbox>
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="max_features_per_tile">
                    Max instances per tile (optional)
                  </FormLabel>
                  <Input
                    id="max_features_per_tile"
                    type="number"
                    placeholder="25000"
                    {...register("max_features_per_tile")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="max_geometric_error">
                    Max geometric error (optional)
                  </FormLabel>
                  <Input
                    id="max_geometric_error"
                    type="number"
                    placeholder="500"
                    {...register("max_geometric_error")}
                  />
                </FormControl>
              </>
            ) : type === "Terrain" ? (
              <>
                <FormControl>
                  <FormLabel htmlFor="max_zoom">Max zoom (optional)</FormLabel>
                  <Input
                    id="max_zoom"
                    type="number"
                    placeholder="auto from resolution"
                    {...register("max_zoom")}
                  />
                </FormControl>
                <FormControl>
                  <Checkbox {...register("to_ellipsoidal_height")}>
                    Convert heights to ellipsoidal (EGM2008)
                  </Checkbox>
                </FormControl>
                <FormControl>
                  <Checkbox {...register("vertex_normals")}>
                    Vertex normals (lighting)
                  </Checkbox>
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="water_key">
                    Water layer (bucket key, optional)
                  </FormLabel>
                  <Controller
                    control={control}
                    name="water_key"
                    render={({ field }) => (
                      <StorageKeyInput
                        id="water_key"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        placeholder="e.g. water/coastline.gpkg"
                        extensions={VECTOR_EXTENSIONS}
                      />
                    )}
                  />
                </FormControl>
              </>
            ) : type === "Polygon" ? (
              <>
                <FormControl>
                  <FormLabel>Building height (m, optional)</FormLabel>
                  <Controller
                    control={control}
                    name="upper_limit_height"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="upper_limit_height"
                        type="number"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        placeholder="e.g. 10 or height * 3"
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Base height (m, optional)</FormLabel>
                  <Controller
                    control={control}
                    name="lower_limit_height"
                    rules={{
                      validate: (v) =>
                        !isInvalidExpression(v) || "Fix the formula",
                    }}
                    render={({ field }) => (
                      <ExpressionInput
                        id="lower_limit_height"
                        type="number"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        fields={fieldNames}
                        features={sampleFeatures}
                        placeholder="0"
                      />
                    )}
                  />
                </FormControl>
                <FormControl>
                  <Checkbox {...register("to_ellipsoidal_height")}>
                    Convert heights to ellipsoidal (EGM2008)
                  </Checkbox>
                </FormControl>
                <FormControl>
                  <Checkbox {...register("remove_bottom_surface")}>
                    Remove bottom surface
                  </Checkbox>
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="max_tile_size_kb">
                    Max tile size in KB (optional)
                  </FormLabel>
                  <Input
                    id="max_tile_size_kb"
                    type="number"
                    placeholder="400"
                    {...register("max_tile_size_kb")}
                  />
                </FormControl>
              </>
            ) : (
              <>
                <FormControl>
                  <FormLabel htmlFor="sample_radius">
                    Sample radius (m, empty = auto)
                  </FormLabel>
                  <Input
                    id="sample_radius"
                    type="number"
                    step="0.01"
                    placeholder="auto"
                    {...register("sample_radius")}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel htmlFor="colorization_image">
                    Colorization raster (bucket key, optional)
                  </FormLabel>
                  <Controller
                    control={control}
                    name="colorization_image"
                    render={({ field }) => (
                      <StorageKeyInput
                        id="colorization_image"
                        value={field.value}
                        onChange={field.onChange}
                        inputRef={field.ref}
                        placeholder="e.g. rasters/orthophoto.tif"
                        extensions={RASTER_EXTENSIONS}
                      />
                    )}
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
                  kind={type as PreviewKind}
                  values={values}
                  features={vectorSample?.features}
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
