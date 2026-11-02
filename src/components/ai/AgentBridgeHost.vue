<script setup lang="ts">
/**
 * AgentBridgeHost.vue — Mount-time starter for the external-agent bridge.
 *
 * A tiny host component (AI build only): starting the persistent agent
 * WebSocket link from a component's setup guarantees it only runs when the
 * app shell actually mounts, and the confirm modal lives here too. Also
 * renders the blue EDGE GLOW while an external agent is actively operating
 * this instance (see agentActive in agentLink.ts — activity, not mere
 * link presence).
 *
 * 外部 agent 桥宿主（仅 AI 构建）：在组件挂载时启动常驻 agent WebSocket
 * 链路；确认弹窗挂在这里；外部 agent 正在操作本实例时渲染边缘微弱蓝光。
 */

import { onMounted } from 'vue'
import { agentActive, startAgentLink } from '@/lib/agentLink'
import AgentConfirmHost from '@/components/ai/AgentConfirmHost.vue'

onMounted(() => {
  startAgentLink()
})
</script>

<template>
  <div v-if="agentActive" class="agent-glow" aria-hidden="true" />
  <AgentConfirmHost />
</template>

<style scoped>
/* Subtle blue edge glow: an inset box-shadow frame that breathes slowly.
 * pointer-events:none — purely informative, never blocks the UI.
 * 微弱蓝色边缘光：内描边 + 呼吸动画，纯提示、不拦截任何交互。 */
.agent-glow {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9990;
  border-radius: 0;
  box-shadow:
    inset 0 0 0 2px rgba(59, 130, 246, 0.22),
    inset 0 0 42px rgba(59, 130, 246, 0.16);
  animation: agent-glow-breathe 3.2s ease-in-out infinite;
}

@keyframes agent-glow-breathe {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
</style>
