import type { TerrainConfig } from "../../../api/types"
import {
  HeightFields,
  type HeightValues,
  type PipelineForm,
  fieldsFor,
  heightDefaults,
  heightFromConfig,
  heightToConfig,
  numText,
} from "./common"

// worker downloads water as a single file
const VECTOR_EXTENSIONS = [".gpkg", ".geojson", ".json", ".fgb"]

export interface TerrainValues extends HeightValues {
  max_zoom: string
  vertex_normals: boolean
  water_key: string
}

const F = fieldsFor<TerrainValues>()

function TerrainFields() {
  return (
    <>
      <F.Number
        name="max_zoom"
        label="Max zoom (optional)"
        placeholder="auto from resolution"
      />
      <HeightFields />
      <F.Checkbox name="vertex_normals" label="Vertex normals (lighting)" />
      <F.StorageKey
        name="water_key"
        label="Water layer (bucket key, optional)"
        placeholder="e.g. water/coastline.gpkg"
        extensions={VECTOR_EXTENSIONS}
      />
    </>
  )
}

export const terrainForm: PipelineForm<TerrainValues, TerrainConfig> = {
  defaults: {
    max_zoom: "",
    ...heightDefaults,
    vertex_normals: true,
    water_key: "",
  },
  toConfig: (v) => {
    const data: Partial<TerrainConfig> = { vertex_normals: !!v.vertex_normals }
    if (v.max_zoom) data.max_zoom = Number(v.max_zoom)
    if (v.water_key) data.water_key = v.water_key
    return { ...data, ...heightToConfig(v) }
  },
  fromConfig: (c) => ({
    max_zoom: numText(c.max_zoom),
    ...heightFromConfig(c),
    vertex_normals: c.vertex_normals !== false,
    water_key: c.water_key || "",
  }),
  Fields: TerrainFields,
}
