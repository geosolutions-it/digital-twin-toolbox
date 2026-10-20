import axios from "axios"
import { API_BASE } from "./config"
import type { AssetsPublic } from "./types"

export async function readAssets(
  params: {
    skip?: number
    limit?: number
    extension?: string
    uploadStatus?: string
  } = {},
): Promise<AssetsPublic> {
  const res = await axios.get(`${API_BASE}/api/v1/assets/`, {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 100,
      extension: params.extension,
      upload_status: params.uploadStatus,
    },
  })
  return res.data
}

export async function readAssetSample(id: string): Promise<unknown> {
  const res = await axios.get(`${API_BASE}/api/v1/assets/${id}/sample`)
  return res.data
}
