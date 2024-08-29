import type { CancelablePromise } from "./core/CancelablePromise"
import { OpenAPI } from "./core/OpenAPI"
import { request as __request } from "./core/request"

import type {
  Body_login_login_access_token,
  Message,
  NewPassword,
  Token,
  UserPublic,
  UpdatePassword,
  UserCreate,
  UserRegister,
  UsersPublic,
  UserUpdate,
  UserUpdateMe,
  AssetPublic,
  AssetsPublic,
  Body_assets_create_asset,
  PipelineCreate,
  PipelinePublic,
  PipelinePublicExtended,
  PipelinesActionTypes,
  PipelinesPublic,
  PipelineUpdate,
} from "./models"

export type LoginData = {
  LoginAccessToken: {
    formData: Body_login_login_access_token
  }
  RecoverPassword: {
    email: string
  }
  ResetPassword: {
    requestBody: NewPassword
  }
  RecoverPasswordHtmlContent: {
    email: string
  }
}

export type UsersData = {
  ReadUsers: {
    limit?: number
    skip?: number
  }
  CreateUser: {
    requestBody: UserCreate
  }
  UpdateUserMe: {
    requestBody: UserUpdateMe
  }
  UpdatePasswordMe: {
    requestBody: UpdatePassword
  }
  RegisterUser: {
    requestBody: UserRegister
  }
  ReadUserById: {
    userId: string
  }
  UpdateUser: {
    requestBody: UserUpdate
    userId: string
  }
  DeleteUser: {
    userId: string
  }
}

export type UtilsData = {
  TestEmail: {
    emailTo: string
  }
}

export type AssetsData = {
  ReadAssets: {
    extension?: string
    limit?: number
    skip?: number
    uploadStatus?: string
  }
  CreateAsset: {
    formData: Body_assets_create_asset
  }
  GetAssetFile: {
    filename: string
  }
  DownloadAsset: {
    id: string
  }
  ReadAssetSample: {
    id: string
  }
  DeleteAsset: {
    id: string
  }
}

export type PipelinesData = {
  ReadPipelines: {
    limit?: number
    skip?: number
  }
  CreatePipeline: {
    requestBody: PipelineCreate
  }
  ProcessPipelineTask: {
    actionType: PipelinesActionTypes
    id: string
  }
  UpdatePipeline: {
    id: string
    requestBody: PipelineUpdate
  }
  ReadPipeline: {
    id: string
  }
  DeletePipeline: {
    id: string
  }
}

export class LoginService {
  /**
   * Login Access Token
   * OAuth2 compatible token login, get an access token for future requests
   * @returns Token Successful Response
   * @throws ApiError
   */
  public static loginAccessToken(
    data: LoginData["LoginAccessToken"],
  ): CancelablePromise<Token> {
    const { formData } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/login/access-token",
      formData: formData,
      mediaType: "application/x-www-form-urlencoded",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Test Token
   * Test access token
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static testToken(): CancelablePromise<UserPublic> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/login/test-token",
    })
  }

  /**
   * Recover Password
   * Password Recovery
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static recoverPassword(
    data: LoginData["RecoverPassword"],
  ): CancelablePromise<Message> {
    const { email } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/password-recovery/{email}",
      path: {
        email,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Reset Password
   * Reset password
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static resetPassword(
    data: LoginData["ResetPassword"],
  ): CancelablePromise<Message> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/reset-password/",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Recover Password Html Content
   * HTML Content for Password Recovery
   * @returns string Successful Response
   * @throws ApiError
   */
  public static recoverPasswordHtmlContent(
    data: LoginData["RecoverPasswordHtmlContent"],
  ): CancelablePromise<string> {
    const { email } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/password-recovery-html-content/{email}",
      path: {
        email,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}

export class UsersService {
  /**
   * Read Users
   * Retrieve users.
   * @returns UsersPublic Successful Response
   * @throws ApiError
   */
  public static readUsers(
    data: UsersData["ReadUsers"] = {},
  ): CancelablePromise<UsersPublic> {
    const { skip = 0, limit = 100 } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/",
      query: {
        skip,
        limit,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Create User
   * Create new user.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static createUser(
    data: UsersData["CreateUser"],
  ): CancelablePromise<UserPublic> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/users/",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Read User Me
   * Get current user.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static readUserMe(): CancelablePromise<UserPublic> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/me",
    })
  }

  /**
   * Delete User Me
   * Delete own user.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static deleteUserMe(): CancelablePromise<Message> {
    return __request(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/users/me",
    })
  }

  /**
   * Update User Me
   * Update own user.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static updateUserMe(
    data: UsersData["UpdateUserMe"],
  ): CancelablePromise<UserPublic> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "PATCH",
      url: "/api/v1/users/me",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Update Password Me
   * Update own password.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static updatePasswordMe(
    data: UsersData["UpdatePasswordMe"],
  ): CancelablePromise<Message> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "PATCH",
      url: "/api/v1/users/me/password",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Register User
   * Create new user without the need to be logged in.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static registerUser(
    data: UsersData["RegisterUser"],
  ): CancelablePromise<UserPublic> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/users/signup",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Read User By Id
   * Get a specific user by id.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static readUserById(
    data: UsersData["ReadUserById"],
  ): CancelablePromise<UserPublic> {
    const { userId } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/{user_id}",
      path: {
        user_id: userId,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Update User
   * Update a user.
   * @returns UserPublic Successful Response
   * @throws ApiError
   */
  public static updateUser(
    data: UsersData["UpdateUser"],
  ): CancelablePromise<UserPublic> {
    const { userId, requestBody } = data
    return __request(OpenAPI, {
      method: "PATCH",
      url: "/api/v1/users/{user_id}",
      path: {
        user_id: userId,
      },
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Delete User
   * Delete a user.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static deleteUser(
    data: UsersData["DeleteUser"],
  ): CancelablePromise<Message> {
    const { userId } = data
    return __request(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/users/{user_id}",
      path: {
        user_id: userId,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}

export class UtilsService {
  /**
   * Test Email
   * Test emails.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static testEmail(
    data: UtilsData["TestEmail"],
  ): CancelablePromise<Message> {
    const { emailTo } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/utils/test-email/",
      query: {
        email_to: emailTo,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}

export class AssetsService {
  /**
   * Read Assets
   * Retrieve assets.
   * @returns AssetsPublic Successful Response
   * @throws ApiError
   */
  public static readAssets(
    data: AssetsData["ReadAssets"] = {},
  ): CancelablePromise<AssetsPublic> {
    const { skip = 0, limit = 100, extension, uploadStatus } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/assets/",
      query: {
        skip,
        limit,
        extension,
        upload_status: uploadStatus,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Create Asset
   * Create new asset.
   * @returns AssetPublic Successful Response
   * @throws ApiError
   */
  public static createAsset(
    data: AssetsData["CreateAsset"],
  ): CancelablePromise<AssetPublic> {
    const { formData } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/assets/",
      formData: formData,
      mediaType: "multipart/form-data",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Get Asset File
   * Download asset by filename.
   * @returns unknown Successful Response
   * @throws ApiError
   */
  public static getAssetFile(
    data: AssetsData["GetAssetFile"],
  ): CancelablePromise<unknown> {
    const { filename } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/assets/files/{filename}",
      path: {
        filename,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Download Asset
   * Download asset by id.
   * @returns unknown Successful Response
   * @throws ApiError
   */
  public static downloadAsset(
    data: AssetsData["DownloadAsset"],
  ): CancelablePromise<unknown> {
    const { id } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/assets/{id}/download",
      path: {
        id,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Read Asset Sample
   * Get asset sample.
   * @returns unknown Successful Response
   * @throws ApiError
   */
  public static readAssetSample(
    data: AssetsData["ReadAssetSample"],
  ): CancelablePromise<unknown> {
    const { id } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/assets/{id}/sample",
      path: {
        id,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Delete Asset
   * Delete an asset.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static deleteAsset(
    data: AssetsData["DeleteAsset"],
  ): CancelablePromise<Message> {
    const { id } = data
    return __request(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/assets/{id}",
      path: {
        id,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}

export class PipelinesService {
  /**
   * Read Pipelines
   * Retrieve pipelines.
   * @returns PipelinesPublic Successful Response
   * @throws ApiError
   */
  public static readPipelines(
    data: PipelinesData["ReadPipelines"] = {},
  ): CancelablePromise<PipelinesPublic> {
    const { skip = 0, limit = 100 } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/pipelines/",
      query: {
        skip,
        limit,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Create Pipeline
   * Create new pipeline.
   * @returns PipelinePublic Successful Response
   * @throws ApiError
   */
  public static createPipeline(
    data: PipelinesData["CreatePipeline"],
  ): CancelablePromise<PipelinePublic> {
    const { requestBody } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/pipelines/",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Process Pipeline Task
   * Run/cancel the pipeline task.
   * @returns unknown Successful Response
   * @throws ApiError
   */
  public static processPipelineTask(
    data: PipelinesData["ProcessPipelineTask"],
  ): CancelablePromise<unknown> {
    const { id, actionType } = data
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/pipelines/{id}/task/{action_type}",
      path: {
        id,
        action_type: actionType,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Update Pipeline
   * Update a pipeline.
   * @returns PipelinePublic Successful Response
   * @throws ApiError
   */
  public static updatePipeline(
    data: PipelinesData["UpdatePipeline"],
  ): CancelablePromise<PipelinePublic> {
    const { id, requestBody } = data
    return __request(OpenAPI, {
      method: "PUT",
      url: "/api/v1/pipelines/{id}",
      path: {
        id,
      },
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Read Pipeline
   * Get pipeline by ID.
   * @returns PipelinePublicExtended Successful Response
   * @throws ApiError
   */
  public static readPipeline(
    data: PipelinesData["ReadPipeline"],
  ): CancelablePromise<PipelinePublicExtended> {
    const { id } = data
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/pipelines/{id}",
      path: {
        id,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }

  /**
   * Delete Pipeline
   * Delete an pipeline.
   * @returns Message Successful Response
   * @throws ApiError
   */
  public static deletePipeline(
    data: PipelinesData["DeletePipeline"],
  ): CancelablePromise<Message> {
    const { id } = data
    return __request(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/pipelines/{id}",
      path: {
        id,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}
