<script setup lang="ts">
import { computed } from 'vue'
import { ICONS } from './icons'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 16 })

const markup = computed(() => ICONS[props.name] ?? '')
</script>

<template>
  <svg
    class="icon"
    :width="props.size"
    :height="props.size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="markup"
  />
</template>

<style scoped>
.icon {
  display: inline-block;
  vertical-align: -2px;
  flex: none;
}
</style>
