import type { TerrainConfig } from "../../../api/types"
import { type PipelineForm, fieldsFor, numText } from "./common"

// worker downloads water as a single file
const VECTOR_EXTENSIONS = [".gpkg", ".geojson", ".json", ".fgb"]

export interface TerrainValues {
  max_zoom: string
  to_ellipsoidal_height: boolean
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
      <F.Checkbox
        name="to_ellipsoidal_height"
        label="Convert heights to ellipsoidal (EGM2008)"
      />
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
    to_ellipsoidal_height: false,
    vertex_normals: true,
    water_key: "",
  },
  toConfig: (v) => {
    const data: Partial<TerrainConfig> = { vertex_normals: !!v.vertex_normals }
    if (v.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (v.max_zoom) data.max_zoom = Number(v.max_zoom)
    if (v.water_key) data.water_key = v.water_key
    return data
  },
  fromConfig: (c) => ({
    max_zoom: numText(c.max_zoom),
    to_ellipsoidal_height: !!c.to_ellipsoidal_height,
    vertex_normals: c.vertex_normals !== false,
    water_key: c.water_key || "",
  }),
  Fields: TerrainFields,
}
