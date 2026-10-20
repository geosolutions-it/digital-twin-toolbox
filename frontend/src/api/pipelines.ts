import axios from "axios"
import { API_BASE } from "./config"
import type {
  Message,
  PipelinePublicExtended,
  PipelinesActionTypes,
  PipelinesPublic,
} from "./types"

export async function readPipelines(
  params: { skip?: number; limit?: number } = {},
): Promise<PipelinesPublic> {
  const res = await axios.get(`${API_BASE}/api/v1/pipelines/`, {
    params: { skip: params.skip ?? 0, limit: params.limit ?? 100 },
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
