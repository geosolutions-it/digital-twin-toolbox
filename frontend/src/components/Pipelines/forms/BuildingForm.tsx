import { Flex, Text } from "@chakra-ui/react"
import { useWatch } from "react-hook-form"
import type { BuildingConfig, BuildingLod } from "../../../api/types"
import {
  type PipelineForm,
  RASTER_EXTENSIONS,
  fieldsFor,
  numText,
} from "./common"

const BUILDING_LODS: readonly BuildingLod[] = ["1.2", "1.3", "2.2"]

function isBuildingLod(v: string | undefined): v is BuildingLod {
  return BUILDING_LODS.includes(v as BuildingLod)
}

export interface BuildingValues {
  point_cloud: string
  lod: string
  orthophoto: string
  texture_resolution: string
  dtm: string
  building_class: string
  ground_class: string
  to_ellipsoidal_height: boolean
  max_tile_size_kb: string
}

const F = fieldsFor<BuildingValues>()

function BuildingFields() {
  const orthophoto = useWatch<BuildingValues, "orthophoto">({
    name: "orthophoto",
  })
  return (
    <>
      <Text fontSize="xs" color="gray.500">
        Roofer reconstructs each footprint from the point cloud, which needs
        ground and building classes and the same CRS as the footprints. The
        footprint attributes are kept.
      </Text>
      <F.StorageKey
        name="point_cloud"
        label="Point cloud (LAS/LAZ file or folder)"
        placeholder="e.g. lidar/tile.laz or lidar/"
        extensions={[".las", ".laz"]}
        required="A point cloud is required."
      />
      <F.Select name="lod" label="Level of detail">
        <option value="2.2">LoD 2.2 (roof shapes)</option>
        <option value="1.3">LoD 1.3 (flat roofs, steps)</option>
        <option value="1.2">LoD 1.2 (one flat roof)</option>
      </F.Select>
      <F.StorageKey
        name="orthophoto"
        label="Orthophoto for the roofs (optional)"
        placeholder="e.g. rasters/orthophoto.tif"
        extensions={RASTER_EXTENSIONS}
      />
      {!!orthophoto && (
        <F.Number
          name="texture_resolution"
          label="Texture resolution (m, optional)"
          step="any"
          placeholder="the orthophoto's"
        />
      )}
      <F.StorageKey
        name="dtm"
        label="Terrain (DTM, optional)"
        placeholder="e.g. rasters/dtm.tif"
        extensions={RASTER_EXTENSIONS}
        help="Lowers building bases onto the terrain on slopes. Same height datum as the point cloud."
      />
      <Flex gap={3}>
        <F.Number
          name="building_class"
          label="Building class"
          placeholder="6"
        />
        <F.Number name="ground_class" label="Ground class" placeholder="2" />
      </Flex>
      <F.Checkbox
        name="to_ellipsoidal_height"
        label="Convert heights to ellipsoidal (EGM2008)"
      />
      <F.Number
        name="max_tile_size_kb"
        label="Max tile size in KB (optional)"
        placeholder="400"
      />
    </>
  )
}

export const buildingForm: PipelineForm<BuildingValues, BuildingConfig> = {
  defaults: {
    point_cloud: "",
    lod: "",
    orthophoto: "",
    texture_resolution: "",
    dtm: "",
    building_class: "",
    ground_class: "",
    to_ellipsoidal_height: false,
    max_tile_size_kb: "",
  },
  toConfig: (v) => {
    const data: Partial<BuildingConfig> = {
      point_cloud: v.point_cloud,
      lod: isBuildingLod(v.lod) ? v.lod : "2.2",
    }
    if (v.orthophoto) data.orthophoto = v.orthophoto
    if (v.dtm) data.dtm = v.dtm
    if (v.building_class) data.building_class = Number(v.building_class)
    if (v.ground_class) data.ground_class = Number(v.ground_class)
    if (v.texture_resolution)
      data.texture_resolution = Number(v.texture_resolution)
    if (v.to_ellipsoidal_height) data.to_ellipsoidal_height = true
    if (v.max_tile_size_kb) data.max_tile_size_kb = Number(v.max_tile_size_kb)
    return data
  },
  fromConfig: (c) => ({
    point_cloud: c.point_cloud || "",
    lod: typeof c.lod === "string" ? c.lod : numText(c.lod),
    orthophoto: c.orthophoto || "",
    texture_resolution: numText(c.texture_resolution),
    dtm: c.dtm || "",
    building_class: numText(c.building_class),
    ground_class: numText(c.ground_class),
    to_ellipsoidal_height: !!c.to_ellipsoidal_height,
    max_tile_size_kb: numText(c.max_tile_size_kb),
  }),
  Fields: BuildingFields,
}
