import type { PolygonConfig } from "../../../api/types"
import {
  type FieldsProps,
  HeightFields,
  type HeightValues,
  type PipelineForm,
  exprText,
  exprValue,
  fieldsFor,
  heightDefaults,
  heightFromConfig,
  heightToConfig,
  numText,
} from "./common"

export interface PolygonValues extends HeightValues {
  upper_limit_height: unknown
  lower_limit_height: unknown
  remove_bottom_surface: boolean
  max_tile_size_kb: string
}

const F = fieldsFor<PolygonValues>()

function PolygonFields(props: FieldsProps) {
  return (
    <>
      <F.Expression
        {...props}
        name="upper_limit_height"
        label="Building height (m, optional)"
        type="number"
        placeholder="e.g. 10 or height * 3"
      />
      <F.Expression
        {...props}
        name="lower_limit_height"
        label="Base height (m, optional)"
        type="number"
        placeholder="0"
      />
      <HeightFields />
      <F.Checkbox name="remove_bottom_surface" label="Remove bottom surface" />
      <F.Number
        name="max_tile_size_kb"
        label="Max tile size in KB (optional)"
        placeholder="400"
      />
    </>
  )
}

export const polygonForm: PipelineForm<PolygonValues, PolygonConfig> = {
  defaults: {
    upper_limit_height: "",
    lower_limit_height: "",
    ...heightDefaults,
    remove_bottom_surface: true,
    max_tile_size_kb: "",
  },
  toConfig: (v) => {
    const data: Partial<PolygonConfig> = {
      remove_bottom_surface: !!v.remove_bottom_surface,
    }
    const upper = exprValue(v.upper_limit_height)
    const lower = exprValue(v.lower_limit_height)
    if (upper !== undefined) data.upper_limit_height = upper
    if (lower !== undefined) data.lower_limit_height = lower
    if (v.max_tile_size_kb) data.max_tile_size_kb = Number(v.max_tile_size_kb)
    return { ...data, ...heightToConfig(v) }
  },
  fromConfig: (c) => ({
    upper_limit_height: exprText(c.upper_limit_height),
    lower_limit_height: exprText(c.lower_limit_height),
    ...heightFromConfig(c),
    remove_bottom_surface: c.remove_bottom_surface !== false,
    max_tile_size_kb: numText(c.max_tile_size_kb),
  }),
  Fields: PolygonFields,
}
