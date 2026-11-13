import type { PointCloudConfig } from "../../../api/types"
import { type PipelineForm, RASTER_EXTENSIONS, fieldsFor } from "./common"

export interface PointCloudValues {
  sample_radius: string
  colorization_image: string
  to_ellipsoidal_height: boolean
  ground_classification: boolean
}

const F = fieldsFor<PointCloudValues>()

function PointCloudFields() {
  return (
    <>
      <F.Number
        name="sample_radius"
        label="Sample radius (m, empty = auto)"
        step="0.01"
        placeholder="auto"
      />
      <F.StorageKey
        name="colorization_image"
        label="Colorization raster (bucket key, optional)"
        placeholder="e.g. rasters/orthophoto.tif"
        extensions={RASTER_EXTENSIONS}
      />
      <F.Checkbox
        name="to_ellipsoidal_height"
        label="Convert to ellipsoidal height"
      />
      <F.Checkbox name="ground_classification" label="Classify ground points" />
    </>
  )
}

export const pointCloudForm: PipelineForm<PointCloudValues, PointCloudConfig> =
  {
    defaults: {
      sample_radius: "",
      colorization_image: "",
      to_ellipsoidal_height: false,
      ground_classification: false,
    },
    toConfig: (v) => {
      const data: Partial<PointCloudConfig> = {}
      if (v.sample_radius) data.sample_radius = Number(v.sample_radius)
      if (v.to_ellipsoidal_height) data.to_ellipsoidal_height = true
      if (v.ground_classification) data.ground_classification = true
      if (v.colorization_image) data.colorization_image = v.colorization_image
      return data
    },
    fromConfig: (c) => ({
      sample_radius: c.sample_radius != null ? String(c.sample_radius) : "",
      colorization_image: c.colorization_image || "",
      to_ellipsoidal_height: !!c.to_ellipsoidal_height,
      ground_classification: !!c.ground_classification,
    }),
    Fields: PointCloudFields,
  }
