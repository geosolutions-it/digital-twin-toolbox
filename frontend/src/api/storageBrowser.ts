import axios from "axios"
import { API_BASE } from "./config"
import type { StorageListing } from "./types"

export async function listStorage(
  prefix = "",
  classify = true,
): Promise<StorageListing> {
  const res = await axios.get(`${API_BASE}/api/v1/storage/`, {
    params: { prefix, classify },
  })
  return res.data
}

export async function uploadToStorage(
  file: File,
  prefix = "",
): Promise<{ key: string }> {
  const form = new FormData()
  form.append("file", file)
  const res = await axios.post(`${API_BASE}/api/v1/storage/upload`, form, {
    params: { prefix },
  })
  return res.data
}

export const modelUrl = (key: string) =>
  `${API_BASE}/api/v1/storage/model?key=${encodeURIComponent(key)}`
