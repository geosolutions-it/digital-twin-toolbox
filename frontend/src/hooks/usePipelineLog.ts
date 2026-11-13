import React from "react"
import { readPipelineLogs } from "../api"
import type { PipelineLogLine } from "../api/types"

// MAX_LINES in backend/app/worker/common/logs.py
const MAX_LINES = 5000
const POLL_MS = 1000

export default function usePipelineLog(
  pipelineId: string,
  { enabled, running }: { enabled: boolean; running: boolean },
) {
  const [lines, setLines] = React.useState<PipelineLogLine[]>([])
  const [loaded, setLoaded] = React.useState(false)
  const [failed, setFailed] = React.useState(false)
  const after = React.useRef(0)

  React.useEffect(() => {
    if (!enabled) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const { data } = await readPipelineLogs(pipelineId, {
          after: after.current,
          limit: MAX_LINES,
        })
        if (stopped) return
        if (data.length) {
          after.current = data[data.length - 1].id
          setLines((prev) => [...prev, ...data].slice(-MAX_LINES))
        }
        setFailed(false)
      } catch {
        if (stopped) return
        setFailed(true)
      }
      setLoaded(true)
      // when running turns false the effect runs once more and reads the final lines
      if (running) timer = setTimeout(poll, POLL_MS)
    }
    poll()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [enabled, pipelineId, running])

  return { lines, loaded, failed }
}
