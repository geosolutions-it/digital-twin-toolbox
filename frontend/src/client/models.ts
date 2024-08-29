export type Asset = {
  filename: string
  content_type?: string | null
  content_size?: number | null
  asset_type?: string | null
  extension?: string | null
  geometry_type?: string | null
  upload_id?: string | null
  upload_status?: string | null
  upload_result: Record<string, unknown> | null
  id?: string
  owner_id: string
}

export type AssetPublic = {
  filename: string
  content_type?: string | null
  content_size?: number | null
  asset_type?: string | null
  extension?: string | null
  geometry_type?: string | null
  upload_id?: string | null
  upload_status?: string | null
  upload_result: Record<string, unknown> | null
  id: string
  owner_id: string
}

export type AssetsPublic = {
  data: Array<AssetPublic>
  count: number
}

export type Body_assets_create_asset = {
  file: Blob | File
}

export type Body_login_login_access_token = {
  grant_type?: string | null
  username: string
  password: string
  scope?: string
  client_id?: string | null
  client_secret?: string | null
}

export type HTTPValidationError = {
  detail?: Array<ValidationError>
}

export type Message = {
  message: string
}

export type NewPassword = {
  token: string
  new_password: string
}

export type PipelineCreate = {
  title: string
  asset_id: string | null
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
}

export type PipelinePublic = {
  title: string
  asset_id: string | null
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
  id: string
  owner_id: string
}

export type PipelinePublicExtended = {
  title: string
  asset_id: string | null
  data: Record<string, unknown> | null
  task_id: string | null
  task_status: string | null
  task_result: Record<string, unknown> | null
  id: string
  owner_id: string
  asset: Asset | null
}

export type PipelineUpdate = {
  data: Record<string, unknown> | null
}

export type PipelinesActionTypes = "run" | "cancel"

export type PipelinesPublic = {
  data: Array<PipelinePublic>
  count: number
}

export type Token = {
  access_token: string
  token_type?: string
}

export type UpdatePassword = {
  current_password: string
  new_password: string
}

export type UserCreate = {
  email: string
  is_active?: boolean
  is_superuser?: boolean
  full_name?: string | null
  password: string
}

export type UserPublic = {
  email: string
  is_active?: boolean
  is_superuser?: boolean
  full_name?: string | null
  id: string
}

export type UserRegister = {
  email: string
  password: string
  full_name?: string | null
}

export type UserUpdate = {
  email?: string | null
  is_active?: boolean
  is_superuser?: boolean
  full_name?: string | null
  password?: string | null
}

export type UserUpdateMe = {
  full_name?: string | null
  email?: string | null
}

export type UsersPublic = {
  data: Array<UserPublic>
  count: number
}

export type ValidationError = {
  loc: Array<string | number>
  msg: string
  type: string
}
