import { Text } from "@chakra-ui/react"
import { useWatch } from "react-hook-form"
import type { InstanceConfig } from "../../../api/types"
import { useStorageListing } from "../StorageKeyInput"
import {
  type FieldsProps,
  type PipelineForm,
  exprText,
  exprValue,
  fieldsFor,
  numText,
} from "./common"

export interface InstanceValues {
  models_prefix: string
  model: unknown
  scale: unknown
  rotation: unknown
  elevation: unknown
  to_ellipsoidal_height: boolean
  max_tile_size_kb: string
  max_geometric_error: string
}

const F = fieldsFor<InstanceValues>()

function InstanceFields(props: FieldsProps) {
  const modelsPrefix =
    useWatch<InstanceValues, "models_prefix">({ name: "models_prefix" }) ?? ""
  const modelsDir = modelsPrefix.slice(0, modelsPrefix.lastIndexOf("/") + 1)
  const modelListing = useStorageListing(modelsDir)
  // worker key is models_prefix + model
  const modelNames = modelListing.data?.files
    .filter(
      (f) =>
        f.key.startsWith(modelsPrefix) && f.key.toLowerCase().endsWith(".glb"),
    )
    .map((f) => f.key.slice(modelsPrefix.length))

  return (
    <>
      <Text fontSize="xs" color="gray.500">
        Point layer: each point places a glb model, instanced in 3D Tiles.
      </Text>
      <F.StorageKey
        name="models_prefix"
        label="Models prefix (optional)"
        placeholder="e.g. models/"
        foldersOnly
      />
      <F.Expression
        {...props}
        name="model"
        label="Model (bucket key or attribute)"
        type="string"
        literals={modelNames}
        placeholder={'e.g. "tree.glb" or lower(type) + ".glb"'}
      />
      <F.Expression
        {...props}
        name="scale"
        label="Scale (optional)"
        type="number"
        placeholder="1"
      />
      <F.Expression
        {...props}
        name="rotation"
        label="Rotation (deg, optional)"
        type="number"
        placeholder="0"
      />
      <F.Expression
        {...props}
        name="elevation"
        label="Elevation (m, optional)"
        type="number"
        placeholder="point Z, e.g. $minZ + 2"
      />
      <F.Checkbox
        name="to_ellipsoidal_height"
        label="Convert heights to ellipsoidal (EGM2008)"
      />
      <F.Number
        name="max_tile_size_kb"
        label="Max tile size in KB (optional)"
        placeholder="1024"
      />
      <F.Number
        name="max_geometric_error"
        label="Max geometric error (optional)"
        placeholder="500"
      />
    </>
  )
}

export const instanceForm: PipelineForm<InstanceValues, InstanceConfig> = {
  defaults: {
    models_prefix: "",
    model: "",
    scale: "",
    rotation: "",
    elevation: "",
    to_ellipsoidal_height: false,
    max_tile_size_kb: "",
    max_geometric_error: "",
  },
  toConfig: (v) => {
    const data: Partial<InstanceConfig> = {}
    if (v.model) data.model = v.model as InstanceConfig["model"]
    if (v.models_prefix) data.models_prefix = v.models_prefix
    const scale = exprValue(v.scale)
    const rotation = exprValue(v.rotation)
    const elevation = exprValue(v.elevation)
    if (scale !== undefined) data.scale = scale
    if (rotation !== undefined) data.rotation = rotation
    if (elevation !== undefined) data.elevation = elevation
    if (v.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (v.max_tile_size_kb) data.max_tile_size_kb = Number(v.max_tile_size_kb)
    if (v.max_geometric_error)
      data.max_geometric_error = Number(v.max_geometric_error)
    return data
  },
  fromConfig: (c) => ({
    models_prefix: c.models_prefix || "",
    model: exprText(c.model) || (typeof c.model === "string" ? c.model : ""),
    scale: exprText(c.scale),
    rotation: exprText(c.rotation),
    elevation: exprText(c.elevation),
    to_ellipsoidal_height: !!c.to_ellipsoidal_height,
    max_tile_size_kb: numText(c.max_tile_size_kb),
    max_geometric_error: numText(c.max_geometric_error),
  }),
  Fields: InstanceFields,
}
