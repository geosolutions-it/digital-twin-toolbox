import { Text } from "@chakra-ui/react"
import type { Axis, MeshConfig } from "../../../api/types"
import { type PipelineForm, fieldsFor, numText } from "./common"

const AXES: { value: Axis; label: string }[] = [
  { value: "X", label: "X" },
  { value: "Y", label: "Y" },
  { value: "Z", label: "Z" },
  { value: "NEGATIVE_X", label: "-X" },
  { value: "NEGATIVE_Y", label: "-Y" },
  { value: "NEGATIVE_Z", label: "-Z" },
]

export interface MeshValues {
  latitude: string
  longitude: string
  altitude: string
  forward_axis: Axis
  up_axis: Axis
  depth: string
  tile_faces_target: string
  texture_image_size: string
  max_geometric_error: string
  decimate_last_depth_level: boolean
}

const F = fieldsFor<MeshValues>()

const axisOptions = AXES.map((a) => (
  <option key={a.value} value={a.value}>
    {a.label}
  </option>
))

function MeshFields() {
  return (
    <>
      <Text fontSize="xs" color="gray.500">
        The mesh origin (0, 0, 0) is placed at this location; vertices are
        metres.
      </Text>
      <F.Number
        name="latitude"
        label="Latitude"
        step="any"
        required="Latitude is required."
      />
      <F.Number
        name="longitude"
        label="Longitude"
        step="any"
        required="Longitude is required."
      />
      <F.Number
        name="altitude"
        label="Altitude (m, ellipsoidal)"
        step="any"
        placeholder="0"
      />
      <F.Select name="forward_axis" label="Forward axis (north)">
        {axisOptions}
      </F.Select>
      <F.Select name="up_axis" label="Up axis">
        {axisOptions}
      </F.Select>
      <F.Number name="depth" label="Depth (optional)" placeholder="4" />
      <F.Number
        name="tile_faces_target"
        label="Faces per tile (optional)"
        placeholder="10000"
      />
      <F.Number
        name="texture_image_size"
        label="Texture size (px, optional)"
        placeholder="512"
      />
      <F.Number
        name="max_geometric_error"
        label="Max geometric error (optional)"
        placeholder="256"
      />
      <F.Checkbox
        name="decimate_last_depth_level"
        label="Decimate the last level"
      />
    </>
  )
}

export const meshForm: PipelineForm<MeshValues, MeshConfig> = {
  defaults: {
    latitude: "",
    longitude: "",
    altitude: "",
    forward_axis: "Y",
    up_axis: "Z",
    depth: "",
    tile_faces_target: "",
    texture_image_size: "",
    max_geometric_error: "",
    decimate_last_depth_level: true,
  },
  toConfig: (v) => {
    const data: Partial<MeshConfig> = {
      latitude: Number(v.latitude || 0),
      longitude: Number(v.longitude || 0),
      altitude: Number(v.altitude || 0),
      forward_axis: v.forward_axis || "Y",
      up_axis: v.up_axis || "Z",
      decimate_last_depth_level: !!v.decimate_last_depth_level,
    }
    if (v.depth) data.depth = Number(v.depth)
    if (v.tile_faces_target)
      data.tile_faces_target = Number(v.tile_faces_target)
    if (v.texture_image_size)
      data.texture_image_size = Number(v.texture_image_size)
    if (v.max_geometric_error)
      data.max_geometric_error = Number(v.max_geometric_error)
    return data
  },
  fromConfig: (c) => ({
    latitude: numText(c.latitude),
    longitude: numText(c.longitude),
    altitude: numText(c.altitude),
    forward_axis: c.forward_axis || "Y",
    up_axis: c.up_axis || "Z",
    depth: numText(c.depth),
    tile_faces_target: numText(c.tile_faces_target),
    texture_image_size: numText(c.texture_image_size),
    max_geometric_error: numText(c.max_geometric_error),
    decimate_last_depth_level: c.decimate_last_depth_level !== false,
  }),
  Fields: MeshFields,
}
