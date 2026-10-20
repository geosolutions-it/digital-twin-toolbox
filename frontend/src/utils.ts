import type { ApiError } from "./client"

const VITE_API_URL = import.meta.env.VITE_API_URL
const ROUTER_BASE_PATH = import.meta.env.VITE_ROUTER_BASE_PATH
const ENABLE_ROUTER_HASH_HISTORY = import.meta.env.VITE_ENABLE_ROUTER_HASH_HISTORY
const PUBLIC_BASE_PATH = import.meta.env.VITE_PUBLIC_BASE_PATH

export const enableHashHistory = () => `${ENABLE_ROUTER_HASH_HISTORY}` === 'True'
export const getPublicBasePath = () => PUBLIC_BASE_PATH || '/'
export const getRouterBasePath = () => ROUTER_BASE_PATH || '/'
export const getViteApiUrl = () => VITE_API_URL

export const handleError = (err: ApiError, showToast: any) => {
  const errDetail = (err.body as any)?.detail
  let errorMessage = errDetail || "Something went wrong."
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    errorMessage = errDetail[0].msg
  }
  showToast("Error", errorMessage, "error")
}
