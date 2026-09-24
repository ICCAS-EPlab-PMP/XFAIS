<template>
  <!--
    AI assistant stub — main (non-Jev) build only.
    vite.config.ts aliases @/components/ai/AssistantBar.vue to this file in
    every mode EXCEPT `jev`, so the main bundle can never pull in the AI
    subtree (providers, agent, skills) through AppShell's async import.
    AI 助手桩组件——仅主线（非 Jev）构建使用。vite.config.ts 在除 jev 外的
    所有模式把 @/components/ai/AssistantBar.vue 别名到本文件，使主线产物
    无法经 AppShell 的异步导入拉入 AI 子树（providers/agent/skills）。
  -->
</template>

<script setup lang="ts">
// Renders nothing / 不渲染任何内容
</script>
