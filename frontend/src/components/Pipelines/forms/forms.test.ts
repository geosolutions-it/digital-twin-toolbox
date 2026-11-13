import { describe, expect, it } from "vitest"
import { PIPELINE_FORMS } from "."
import type { PipelineType } from "../../../api/types"

const TYPES = Object.keys(PIPELINE_FORMS) as PipelineType[]

// what an untouched form sends; the backend fills in the rest
const UNTOUCHED: Record<PipelineType, object> = {
  PointCloud: {},
  Polygon: { remove_bottom_surface: true },
  Instance: {},
  Terrain: { vertex_normals: true },
  Mesh: {
    latitude: 0,
    longitude: 0,
    altitude: 0,
    forward_axis: "Y",
    up_axis: "Z",
    decimate_last_depth_level: true,
  },
  CityGML: {},
  Building: { point_cloud: "", lod: "2.2" },
}

// every field set to a non-default value, so a field lost on load or save shows up
const SAVED: Record<PipelineType, object> = {
  PointCloud: {
    sample_radius: 0.5,
    colorization_image: "rasters/ortho.tif",
    to_ellipsoidal_height: true,
    ground_classification: true,
  },
  Polygon: {
    upper_limit_height: ["*", ["property", "floors"], 3],
    lower_limit_height: 2,
    to_ellipsoidal_height: true,
    remove_bottom_surface: false,
    max_tile_size_kb: 300,
  },
  Instance: {
    model: ["concat", ["property", "kind"], ".glb"],
    models_prefix: "models/",
    scale: 2,
    rotation: ["property", "angle"],
    elevation: 10,
    to_ellipsoidal_height: true,
    max_tile_size_kb: 512,
    max_geometric_error: 100,
  },
  Terrain: {
    max_zoom: 14,
    to_ellipsoidal_height: true,
    vertex_normals: false,
    water_key: "water/sea.gpkg",
  },
  Mesh: {
    latitude: 45.65,
    longitude: 13.77,
    altitude: 12,
    forward_axis: "NEGATIVE_Z",
    up_axis: "Y",
    depth: 3,
    tile_faces_target: 5000,
    texture_image_size: 1024,
    max_geometric_error: 128,
    decimate_last_depth_level: false,
  },
  CityGML: {
    lod: 2,
    to_ellipsoidal_height: true,
    horizontal_epsg: 6708,
    vertical_epsg: 3855,
    orthophoto: "rasters/ortho.tif",
    texture_resolution: 0.2,
    max_tile_size_kb: 300,
  },
  Building: {
    point_cloud: "lidar/",
    lod: "1.3",
    orthophoto: "rasters/ortho.tif",
    dtm: "rasters/dtm.tif",
    building_class: 7,
    ground_class: 3,
    texture_resolution: 0.25,
    to_ellipsoidal_height: true,
    max_tile_size_kb: 300,
  },
}

describe.each(TYPES)("%s form", (type) => {
  const form = PIPELINE_FORMS[type]

  it("sends the expected config when untouched", () => {
    expect(form.toConfig(form.defaults)).toEqual(UNTOUCHED[type])
  })

  it("loads an empty config as the defaults", () => {
    expect(form.fromConfig({})).toEqual(form.defaults)
  })

  it("saves a loaded config unchanged", () => {
    const values = { ...form.defaults, ...form.fromConfig(SAVED[type]) }
    expect(form.toConfig(values)).toEqual(SAVED[type])
  })
})

it("Instance keeps a plain model name", () => {
  const form = PIPELINE_FORMS.Instance
  const values = { ...form.defaults, ...form.fromConfig({ model: "tree.glb" }) }
  expect(form.toConfig(values)).toEqual({ model: "tree.glb" })
})
