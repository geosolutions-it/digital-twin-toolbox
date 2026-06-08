export const CELERY_IN_PROGRESS_STATUSES = ["PENDING", "STARTED"] as const

export function isCeleryTaskInProgress(status?: string | null): boolean {
  return (CELERY_IN_PROGRESS_STATUSES as readonly string[]).includes(
    status ?? "",
  )
}

export function celeryTaskStatusLabel(status?: string | null): string {
  if (isCeleryTaskInProgress(status)) return "PENDING"
  return status ?? "READY"
}

export function celeryTaskStatusColor(status?: string | null): string {
  if (isCeleryTaskInProgress(status)) return "yellow"
  if (status === "SUCCESS") return "green"
  return "red"
}
