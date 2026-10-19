import axios from "axios"
import { OpenAPI } from "../client"

export interface PipelineBatchRequest {
  prefix: string
  pipeline?: string
  data?: Record<string, unknown> | null
  title?: string | null
}

export interface PipelineBatchResponse {
  batch_id: string
  count: number
  pipeline_ids: string[]
}

export async function createPipelineBatch(
  body: PipelineBatchRequest,
): Promise<PipelineBatchResponse> {
  const token = localStorage.getItem("access_token") || ""
  const res = await axios.post(
    `${OpenAPI.BASE}/api/v1/pipelines/batch`,
    body,
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
  )
  return res.data
}

export interface PipelineSourceRequest {
  key: string
  pipeline?: string
  data?: Record<string, unknown> | null
  title?: string | null
}

export async function createPipelineSource(
  body: PipelineSourceRequest,
): Promise<{ id: string }> {
  const token = localStorage.getItem("access_token") || ""
  const res = await axios.post(
    `${OpenAPI.BASE}/api/v1/pipelines/source`,
    body,
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
  )
  return res.data
}

export async function finalizePipelineBatch(batchId: string): Promise<{ ok: boolean }> {
  const token = localStorage.getItem("access_token") || ""
  const res = await axios.post(
    `${OpenAPI.BASE}/api/v1/pipelines/batch/${batchId}/finalize`,
    {},
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
  )
  return res.data
}
