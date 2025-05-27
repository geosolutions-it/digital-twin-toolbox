import type { ApiError } from "./client"

export const emailPattern = {
  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
  message: "Invalid email address",
}

export const namePattern = {
  value: /^[A-Za-z\s\u00C0-\u017F]{1,30}$/,
  message: "Invalid name",
}

export const passwordRules = (isRequired = true) => {
  const rules: any = {
    minLength: {
      value: 8,
      message: "Password must be at least 8 characters",
    },
  }

  if (isRequired) {
    rules.required = "Password is required"
  }

  return rules
}

const VITE_API_URL = import.meta.env.VITE_API_URL
const ROUTER_BASE_PATH = import.meta.env.VITE_ROUTER_BASE_PATH
const ENABLE_USERS_MANAGEMENT = import.meta.env.VITE_ENABLE_USERS_MANAGEMENT
const ENABLE_ROUTER_HASH_HISTORY = import.meta.env.VITE_ENABLE_ROUTER_HASH_HISTORY
const PUBLIC_BASE_PATH = import.meta.env.VITE_PUBLIC_BASE_PATH

// using template to prevent removal from build
export const hideUserSections = () => `${ENABLE_USERS_MANAGEMENT}` === 'False'
export const enableHashHistory = () => `${ENABLE_ROUTER_HASH_HISTORY}` === 'True'
export const getPublicBasePath = () => PUBLIC_BASE_PATH || '/'
export const getRouterBasePath = () => ROUTER_BASE_PATH || '/'
export const getViteApiUrl = () => VITE_API_URL

export const confirmPasswordRules = (
  getValues: () => any,
  isRequired = true,
) => {
  const rules: any = {
    validate: (value: string) => {
      const password = getValues().password || getValues().new_password
      return value === password ? true : "The passwords do not match"
    },
  }

  if (isRequired) {
    rules.required = "Password confirmation is required"
  }

  return rules
}

export const handleError = (err: ApiError, showToast: any) => {
  const errDetail = (err.body as any)?.detail
  let errorMessage = errDetail || "Something went wrong."
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    errorMessage = errDetail[0].msg
  }
  showToast("Error", errorMessage, "error")
}
