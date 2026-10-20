const VITE_API_URL = import.meta.env.VITE_API_URL
const ROUTER_BASE_PATH = import.meta.env.VITE_ROUTER_BASE_PATH
const ENABLE_ROUTER_HASH_HISTORY = import.meta.env.VITE_ENABLE_ROUTER_HASH_HISTORY
const PUBLIC_BASE_PATH = import.meta.env.VITE_PUBLIC_BASE_PATH

export const enableHashHistory = () => `${ENABLE_ROUTER_HASH_HISTORY}` === 'True'
export const getPublicBasePath = () => PUBLIC_BASE_PATH || '/'
export const getRouterBasePath = () => ROUTER_BASE_PATH || '/'
export const getViteApiUrl = () => VITE_API_URL
