<script setup lang="ts">
import { computed } from 'vue'
import { useVersions } from './versions'

const { root, current, data } = useVersions()
const release = computed(() => data.value?.release)
const show = computed(() => release.value && release.value !== current)
</script>

<template>
  <div v-if="show" class="warning custom-block">
    <p v-if="current === 'latest'">
      You are reading the docs of the development version (<code>main</code>). The newest release is
      <a :href="`${root}${release}/`">{{ release }}</a>.
    </p>
    <p v-else>
      You are reading the docs for <code>{{ current }}</code>. The newest release is
      <a :href="`${root}${release}/`">{{ release }}</a>.
    </p>
  </div>
</template>
