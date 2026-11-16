import { useData } from 'vitepress'
import { onMounted, ref } from 'vue'

export interface Versions {
  release: string | null
  versions: string[]
}

const data = ref<Versions | null>(null)
let loading: Promise<void> | null = null

// Site root is the base without its last segment: /repo/v1.0.0/ -> /repo/
export function useVersions() {
  const { site, theme } = useData()
  const base = site.value.base
  const root = base.replace(/[^/]+\/$/, '')
  const current = theme.value.version as string
  onMounted(() => {
    loading ??= fetch(`${root}versions.json`)
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        data.value = json
      })
      .catch(() => {})
  })
  return { base, root, current, data }
}
