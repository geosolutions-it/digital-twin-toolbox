import type { PipelinePublic, PipelineType } from "../../api/types"

export const PER_PAGE = 10

export function pipelineType(p: PipelinePublic): PipelineType {
  return p.source?.pipeline ?? "PointCloud"
}

export type RowAction = "run" | "cancel" | "delete" | "rebuild"
export type BatchAction = "run" | "cancel" | "rebuild"

export function zipName(name: string) {
  return (name || "").replace(/(\.zip)+$/i, "")
}
