import axios from "axios"
import { API_BASE } from "./config"
import type {
  FinalizeQueued,
  HeightReference,
  MeshBbox,
  Message,
  PipelineBatchActionResult,
  PipelineBatchCreate,
  PipelineBatchCreated,
  PipelineBatchUpdated,
  PipelineConfigInput,
  PipelineCreated,
  PipelinePublic,
  PipelineSourceCreate,
  PipelinesActionTypes,
  VectorFields,
  VectorSample,
} from "./types"

export async function createPipelineBatch(
  body: PipelineBatchCreate,
): Promise<PipelineBatchCreated> {
  const res = await axios.post(`${API_BASE}/api/v1/pipelines/batch`, body)
  return res.data
}

export async function createPipelineSource(
  body: PipelineSourceCreate,
): Promise<PipelineCreated> {
  const res = await axios.post(`${API_BASE}/api/v1/pipelines/source`, body)
  return res.data
}

export async function updatePipelineConfig(
  id: string,
  data: PipelineConfigInput,
  sourceKey?: string,
): Promise<PipelinePublic> {
  const res = await axios.put(`${API_BASE}/api/v1/pipelines/${id}`, {
    data,
    ...(sourceKey ? { source_key: sourceKey } : {}),
  })
  return res.data
}

export async function updateBatchConfig(
  batchId: string,
  data: PipelineConfigInput,
  prefix?: string,
): Promise<PipelineBatchUpdated> {
  const res = await axios.put(`${API_BASE}/api/v1/pipelines/batch/${batchId}`, {
    data,
    ...(prefix ? { prefix } : {}),
  })
  return res.data
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

export async function getVectorSample(params: {
  key?: string
  prefix?: string
  limit?: number
  height_reference?: HeightReference
  vertical_epsg?: number
}): Promise<VectorSample> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/vector-sample`, {
    params: {
      key: params.key,
      prefix: params.prefix,
      limit: params.limit,
      height_reference: params.height_reference,
      vertical_epsg: params.vertical_epsg,
    },
  })
  return res.data
}

export async function getMeshBbox(params: {
  key?: string
  prefix?: string
}): Promise<MeshBbox> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/mesh-bbox`, {
    params: { key: params.key, prefix: params.prefix },
  })
  return res.data
}

export async function finalizePipelineBatch(
  batchId: string,
): Promise<FinalizeQueued> {
  const res = await axios.post(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}/finalize`,
    {},
  )
  return res.data
}

export async function processPipelineBatchTask(
  batchId: string,
  actionType: PipelinesActionTypes,
): Promise<PipelineBatchActionResult> {
  const res = await axios.post(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}/task/${actionType}`,
  )
  return res.data
}

export async function deletePipelineBatch(batchId: string): Promise<Message> {
  const res = await axios.delete(
    `${API_BASE}/api/v1/pipelines/batch/${batchId}`,
  )
  return res.data
}
