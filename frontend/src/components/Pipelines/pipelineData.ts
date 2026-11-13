import {
  type PipelinePublic,
  type PipelineType,
  isPipelineType,
} from "../../api/types"

export const PER_PAGE = 10

// JSON columns the API does not type yet
type PipelineSource = { key?: string; pipeline?: string }
export type TaskResult = {
  tileset?: string
  download?: string
  artifacts?: Artifact[]
}

export const sourceOf = (p: PipelinePublic) =>
  p.source as PipelineSource | null | undefined

export function pipelineType(p: PipelinePublic): PipelineType {
  const t = sourceOf(p)?.pipeline
  return isPipelineType(t) ? t : "PointCloud"
}

export type RowAction = "run" | "cancel" | "delete" | "rebuild"
export type BatchAction = "run" | "cancel" | "rebuild"

export function zipName(name: string) {
  return (name || "").replace(/(\.zip)+$/i, "")
}

export type Artifact = { name: string; url: string; size?: number }
