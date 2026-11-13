import type {
  AnyPipelineConfig,
  PipelineConfigInput,
  PipelinePublic,
  PipelineType,
} from "../../../api/types"
import { type BuildingValues, buildingForm } from "./BuildingForm"
import { type CityGMLValues, cityGMLForm } from "./CityGMLForm"
import { type InstanceValues, instanceForm } from "./InstanceForm"
import { type MeshValues, meshForm } from "./MeshForm"
import { type PointCloudValues, pointCloudForm } from "./PointCloudForm"
import { type PolygonValues, polygonForm } from "./PolygonForm"
import { type TerrainValues, terrainForm } from "./TerrainForm"
import type { PipelineForm } from "./common"

// a Record so a pipeline type added to the backend fails tsc until it has a form
export const PIPELINE_FORMS: Record<PipelineType, PipelineForm<any, any>> = {
  PointCloud: pointCloudForm,
  Polygon: polygonForm,
  Instance: instanceForm,
  Terrain: terrainForm,
  Mesh: meshForm,
  CityGML: cityGMLForm,
  Building: buildingForm,
}

interface SharedValues {
  prefix: string
  title: string
  pipelineType: PipelineType
}

type FormFieldValues = PointCloudValues &
  PolygonValues &
  InstanceValues &
  TerrainValues &
  MeshValues &
  CityGMLValues &
  BuildingValues

/** One form holds every type's fields, so values survive switching the type. */
export type PipelineFormValues = SharedValues & FormFieldValues

export const FORM_DEFAULTS = Object.assign(
  {},
  ...Object.values(PIPELINE_FORMS).map((form) => form.defaults),
) as FormFieldValues

export function formValuesFromConfig(
  type: PipelineType,
  data: PipelinePublic["data"] | undefined,
): Partial<PipelineFormValues> {
  // stored rows may predate validation, so fromConfig checks value types itself
  return PIPELINE_FORMS[type].fromConfig((data ?? {}) as AnyPipelineConfig)
}

export function configFromValues(
  type: PipelineType,
  values: PipelineFormValues,
): PipelineConfigInput {
  return PIPELINE_FORMS[type].toConfig(values)
}
