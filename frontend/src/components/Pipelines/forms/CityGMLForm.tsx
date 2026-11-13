import { useWatch } from "react-hook-form"
import type { CityGMLConfig } from "../../../api/types"
import {
  HeightFields,
  type HeightValues,
  type PipelineForm,
  RASTER_EXTENSIONS,
  fieldsFor,
  heightDefaults,
  heightFromConfig,
  heightToConfig,
  numText,
} from "./common"

export interface CityGMLValues extends HeightValues {
  lod: string
  horizontal_epsg: string
  orthophoto: string
  texture_resolution: string
  max_tile_size_kb: string
}

const F = fieldsFor<CityGMLValues>()

function CityGMLFields() {
  const orthophoto = useWatch<CityGMLValues, "orthophoto">({
    name: "orthophoto",
  })
  return (
    <>
      <F.Select name="lod" label="Level of detail">
        <option value="">Highest available</option>
        {[0, 1, 2, 3, 4].map((l) => (
          <option key={l} value={String(l)}>
            Up to LoD{l}
          </option>
        ))}
      </F.Select>
      <HeightFields />
      <F.Number
        name="horizontal_epsg"
        label="Horizontal EPSG (optional)"
        placeholder="from the file srsName"
      />
      <F.StorageKey
        name="orthophoto"
        label="Orthophoto for the roofs (optional)"
        placeholder="e.g. rasters/orthophoto.tif"
        extensions={RASTER_EXTENSIONS}
        help="Textures the roofs and adds a roof_color attribute."
      />
      {!!orthophoto && (
        <F.Number
          name="texture_resolution"
          label="Texture resolution (m, optional)"
          step="any"
          placeholder="the orthophoto's"
        />
      )}
      <F.Number
        name="max_tile_size_kb"
        label="Max tile size in KB (optional)"
        placeholder="400"
      />
    </>
  )
}

export const cityGMLForm: PipelineForm<CityGMLValues, CityGMLConfig> = {
  defaults: {
    lod: "",
    ...heightDefaults,
    horizontal_epsg: "",
    orthophoto: "",
    texture_resolution: "",
    max_tile_size_kb: "",
  },
  toConfig: (v) => {
    const data: Partial<CityGMLConfig> = {}
    if (v.lod) data.lod = Number(v.lod)
    if (v.orthophoto) data.orthophoto = v.orthophoto
    if (v.orthophoto && v.texture_resolution)
      data.texture_resolution = Number(v.texture_resolution)
    if (v.horizontal_epsg) data.horizontal_epsg = Number(v.horizontal_epsg)
    if (v.max_tile_size_kb) data.max_tile_size_kb = Number(v.max_tile_size_kb)
    return { ...data, ...heightToConfig(v) }
  },
  fromConfig: (c) => ({
    lod: typeof c.lod === "string" ? c.lod : numText(c.lod),
    ...heightFromConfig(c),
    horizontal_epsg: numText(c.horizontal_epsg),
    orthophoto: c.orthophoto || "",
    texture_resolution: numText(c.texture_resolution),
    max_tile_size_kb: numText(c.max_tile_size_kb),
  }),
  Fields: CityGMLFields,
}
