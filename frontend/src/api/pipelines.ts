import axios from "axios"
import { API_BASE } from "./config"
import type {
  Message,
  PipelinePublicExtended,
  PipelinesActionTypes,
  PipelinesOverview,
  PipelinesPublic,
} from "./types"

export async function readPipelines(
  params: { skip?: number; limit?: number; batch_id?: string } = {},
): Promise<PipelinesPublic> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/`, {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 100,
      ...(params.batch_id ? { batch_id: params.batch_id } : {}),
    },
  })
  return res.data
}

export async function readPipelinesOverview(
  params: { skip?: number; limit?: number } = {},
): Promise<PipelinesOverview> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/overview`, {
    params: { skip: params.skip ?? 0, limit: params.limit ?? 10 },
  })
  return res.data
}

export async function readPipeline(id: string): Promise<PipelinePublicExtended> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/${id}`)
  return res.data
}

export async function deletePipeline(id: string): Promise<Message> {
  const res = await axios.delete(`${API_BASE}/api/v1/pipelines/${id}`)
  return res.data
}

export async function processPipelineTask(
  id: string,
  actionType: PipelinesActionTypes,
): Promise<unknown> {
  const res = await axios.post(
    `${API_BASE}/api/v1/pipelines/${id}/task/${actionType}`,
  )
  return res.data
}
