export type Message = {
  message: string
}

export type PipelinePublic = {
  title: string
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
  id: string
  owner_id: string
  stage?: string | null
}

export type PipelineLogLine = {
  id: number
  created_at: string
  level: string
  message: string
  stage: string | null
}

export type PipelineLogs = {
  data: Array<PipelineLogLine>
}

export type PipelinesActionTypes = "run" | "cancel"

export type PipelinesPublic = {
  data: Array<PipelinePublic>
  count: number
}

export type PipelineBatchCounts = {
  success: number
  running: number
  ready: number
  failed: number
}

export type PipelineBatchSummary = {
  batch_id: string
  label: string
  source: string | null
  output_prefix: string | null
  output_url?: string | null
  pipeline: string | null
  sample_key: string | null
  data: Record<string, unknown> | null
  total: number
  counts: PipelineBatchCounts
}

export type PipelineOverviewEntry = {
  kind: "batch" | "pipeline"
  batch: PipelineBatchSummary | null
  pipeline: PipelinePublic | null
}

export type PipelinesOverview = {
  data: Array<PipelineOverviewEntry>
  count: number
}
