import axios from "axios"
import { OpenAPI } from "../client"

export interface StorageFile {
  key: string
  name: string
  size: number
}

export interface StorageListing {
  prefix: string
  folders: string[]
  files: StorageFile[]
}

export async function listStorage(prefix = ""): Promise<StorageListing> {
  const token = localStorage.getItem("access_token") || ""
  const res = await axios.get(`${OpenAPI.BASE}/api/v1/storage/`, {
    params: { prefix },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  return res.data
}
