<script setup lang="ts">
import { useRoute } from 'vitepress'
import { useVersions } from './versions'

const { base, root, current, data } = useVersions()
const route = useRoute()

function label(v: string) {
  if (v === 'latest') return 'latest (main)'
  return v === data.value?.release ? `${v} (release)` : v
}

function go(event: Event) {
  const target = (event.target as HTMLSelectElement).value
  const page = route.path.startsWith(base) ? route.path.slice(base.length) : ''
  window.location.href = `${root}${target}/${page}`
}
</script>

<template>
  <div v-if="data" class="version-switcher">
    <select :value="current" aria-label="Documentation version" @change="go">
      <option v-for="v in data.versions" :key="v" :value="v">{{ label(v) }}</option>
    </select>
  </div>
</template>

<style scoped>
.version-switcher {
  display: flex;
  align-items: center;
  padding-left: 12px;
}
select {
  font-size: 13px;
  font-weight: 500;
  color: var(--vp-c-text-1);
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  padding: 2px 6px;
  cursor: pointer;
}
</style>
