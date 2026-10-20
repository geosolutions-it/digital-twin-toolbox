export type Asset = {
  filename: string
  content_type?: string | null
  content_size?: number | null
  asset_type?: string | null
  extension?: string | null
  geometry_type?: string | null
  upload_id?: string | null
  upload_status?: string | null
  upload_result: Record<string, unknown> | null
  id?: string
  owner_id: string
}

export type AssetPublic = {
  filename: string
  content_type?: string | null
  content_size?: number | null
  asset_type?: string | null
  extension?: string | null
  geometry_type?: string | null
  upload_id?: string | null
  upload_status?: string | null
  upload_result: Record<string, unknown> | null
  id: string
  owner_id: string
}

export type AssetsPublic = {
  data: Array<AssetPublic>
  count: number
}

export type Message = {
  message: string
}

export type PipelinePublic = {
  title: string
  asset_id: string | null
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
  id: string
  owner_id: string
}

export type PipelinePublicExtended = {
  title: string
  asset_id: string | null
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
  id: string
  owner_id: string
  asset: Asset | null
}

export type PipelineUpdate = {
  data: Record<string, unknown> | null
}

export type PipelinesActionTypes = "run" | "cancel"

export type PipelinesPublic = {
  data: Array<PipelinePublic>
  count: number
}
