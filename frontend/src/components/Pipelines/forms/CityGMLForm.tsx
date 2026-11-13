import { useWatch } from "react-hook-form"
import type { CityGMLConfig } from "../../../api/types"
import {
  type PipelineForm,
  RASTER_EXTENSIONS,
  fieldsFor,
  numText,
} from "./common"

export interface CityGMLValues {
  lod: string
  to_ellipsoidal_height: boolean
  horizontal_epsg: string
  vertical_epsg: string
  orthophoto: string
  texture_resolution: string
  max_tile_size_kb: string
}

const F = fieldsFor<CityGMLValues>()

function CityGMLFields() {
  const [ellipsoidal, orthophoto] = useWatch<
    CityGMLValues,
    ["to_ellipsoidal_height", "orthophoto"]
  >({ name: ["to_ellipsoidal_height", "orthophoto"] })
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
      <F.Checkbox
        name="to_ellipsoidal_height"
        label="Convert heights to ellipsoidal"
        help="Uses the height datum declared in the file; otherwise the vertical EPSG below (EGM2008 when empty)."
      />
      <F.Number
        name="horizontal_epsg"
        label="Horizontal EPSG (optional)"
        placeholder="from the file srsName"
      />
      {ellipsoidal && (
        <F.Number
          name="vertical_epsg"
          label="Vertical EPSG (optional)"
          placeholder="3855"
        />
      )}
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
    to_ellipsoidal_height: false,
    horizontal_epsg: "",
    vertical_epsg: "",
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
    if (v.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (v.horizontal_epsg) data.horizontal_epsg = Number(v.horizontal_epsg)
    if (v.vertical_epsg) data.vertical_epsg = Number(v.vertical_epsg)
    if (v.max_tile_size_kb) data.max_tile_size_kb = Number(v.max_tile_size_kb)
    return data
  },
  fromConfig: (c) => ({
    lod: typeof c.lod === "string" ? c.lod : numText(c.lod),
    to_ellipsoidal_height: !!c.to_ellipsoidal_height,
    horizontal_epsg: numText(c.horizontal_epsg),
    vertical_epsg: numText(c.vertical_epsg),
    orthophoto: c.orthophoto || "",
    texture_resolution: numText(c.texture_resolution),
    max_tile_size_kb: numText(c.max_tile_size_kb),
  }),
  Fields: CityGMLFields,
}
