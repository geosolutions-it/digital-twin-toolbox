import type { components } from "./schema.gen"

type S = components["schemas"]

export type Message = S["Message"]
export type PipelinePublic = S["PipelinePublic"]
export type PipelineLogLine = S["PipelineLogPublic"]
export type PipelineLogs = S["PipelineLogsPublic"]
export type PipelinesActionTypes = S["PipelinesActionTypes"]
export type PipelinesPublic = S["PipelinesPublic"]
export type PipelineBatchCounts = S["PipelineBatchCounts"]
export type PipelineBatchSummary = S["PipelineBatchSummary"]
export type PipelineOverviewEntry = S["PipelineOverviewEntry"]
export type PipelinesOverview = S["PipelinesOverview"]
export type PipelineBatchCreate = S["PipelineBatchCreate"]
export type PipelineSourceCreate = S["PipelineSourceCreate"]
export type PipelineType = NonNullable<PipelineSourceCreate["pipeline"]>
export type PipelineCreated = S["PipelineCreated"]
export type PipelineBatchCreated = S["PipelineBatchCreated"]
export type PipelineBatchUpdated = S["PipelineBatchUpdated"]
export type PipelineActionResult = S["PipelineActionResult"]
export type PipelineBatchActionResult = S["PipelineBatchActionResult"]
export type FinalizeQueued = S["FinalizeQueued"]

export type VectorFields = S["VectorFields"]
export type VectorSample = S["VectorSample"]
export type SampleFeature = S["SampleFeature"]
export type MeshBbox = S["MeshBbox"]

export type PointCloudConfig = S["PointCloudConfig"]
export type MeshConfig = S["MeshConfig"]
export type CityGMLConfig = S["CityGMLConfig"]
export type BuildingConfig = S["BuildingConfig"]
export type Axis = MeshConfig["forward_axis"]
export type BuildingLod = BuildingConfig["lod"]
export type PolygonConfig = S["PolygonConfig"]
export type TerrainConfig = S["TerrainConfig"]
export type InstanceConfig = S["InstanceConfig"]

export type PipelineConfig =
  | PointCloudConfig
  | PolygonConfig
  | TerrainConfig
  | InstanceConfig
  | MeshConfig
  | CityGMLConfig
  | BuildingConfig

// openapi-typescript marks defaulted fields required; a sent config may omit them
export type PipelineConfigInput = Partial<PipelineConfig>

type KeysOfUnion<T> = T extends T ? keyof T : never
type ValueInUnion<T, K extends PropertyKey> = T extends Record<K, infer V> ? V : never

// every key of every pipeline config, for code that reads a stored config of any type
export type AnyPipelineConfig = {
  [K in KeysOfUnion<PipelineConfig>]?: ValueInUnion<PipelineConfig, K>
}
