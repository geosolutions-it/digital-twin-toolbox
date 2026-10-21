import axios from "axios"
import { API_BASE } from "./config"

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
  const res = await axios.post(`${API_BASE}/api/v1/pipelines/batch`, body)
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
  const res = await axios.post(`${API_BASE}/api/v1/pipelines/source`, body)
  return res.data
}

export async function updatePipelineConfig(
  id: string,
  data: Record<string, unknown> | null,
): Promise<unknown> {
  const res = await axios.put(`${API_BASE}/api/v1/pipelines/${id}`, { data })
  return res.data
}

export async function updateBatchConfig(
  batchId: string,
  data: Record<string, unknown> | null,
): Promise<{ batch_id: string; count: number }> {
  const res = await axios.put(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}`,
    { data },
  )
  return res.data
}

export interface VectorFields {
  count: number
  fields: { name: string; type: string }[]
  properties: Record<string, unknown>
}

export async function getVectorFields(params: {
  key?: string
  prefix?: string
}): Promise<VectorFields> {
  const qs = new URLSearchParams()
  if (params.key) qs.set("key", params.key)
  if (params.prefix) qs.set("prefix", params.prefix)
  const res = await axios.get(
    `${API_BASE}/api/v1/pipelines/vector-fields?${qs.toString()}`,
  )
  return res.data
}

export async function finalizePipelineBatch(batchId: string): Promise<{ ok: boolean }> {
  const res = await axios.post(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}/finalize`,
    {},
  )
  return res.data
}

export async function processPipelineBatchTask(
  batchId: string,
  actionType: "run" | "cancel",
): Promise<{ batch_id: string; count: number; affected: number }> {
  const res = await axios.post(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}/task/${actionType}`,
  )
  return res.data
}

export async function deletePipelineBatch(
  batchId: string,
): Promise<{ message: string }> {
  const res = await axios.delete(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}`,
  )
  return res.data
}
