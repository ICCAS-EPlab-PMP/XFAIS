<script setup lang="ts">
/**
 * AgentConfirmHost.vue — In-app confirmation modal for external AI agents.
 *
 * Rendered only in the AI build (App.vue). When an MCP agent requests a KEY
 * action it sends a `confirm` command; this host shows the request (plus the
 * spotlighted target, when an aiId is given) and the operation only proceeds
 * after the user clicks 确认 — the agent never gets a silent yes.
 *
 * 外部 AI agent 的应用内确认弹窗（仅 AI 构建挂载）。agent 请求关键操作时
 * 发送 confirm 命令；此处展示请求内容（带 aiId 时聚光目标控件），用户点
 * 「确认」后才继续——agent 永远拿不到无声的 yes。
 */

import { pendingConfirm, resolveConfirm } from '@/lib/agentLink'
</script>

<template>
  <Teleport to="body">
    <div v-if="pendingConfirm" class="agc-backdrop" role="dialog" aria-modal="true">
      <div class="agc-dialog">
        <div class="agc-title">AI 助手请求执行操作</div>
        <p class="agc-message">{{ pendingConfirm.message }}</p>
        <p v-if="pendingConfirm.note" class="agc-note">{{ pendingConfirm.note }}</p>
        <div class="agc-actions">
          <button type="button" class="agc-btn agc-btn--cancel" @click="resolveConfirm(false)">取消</button>
          <button type="button" class="agc-btn agc-btn--ok" data-ai-id="agent:confirm-ok" @click="resolveConfirm(true)">确认</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.agc-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9500;
}

.agc-dialog {
  min-width: 320px;
  max-width: 460px;
  background: var(--surface-1, #ffffff);
  color: var(--text-1, #0f172a);
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 10px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.25);
  padding: 18px 20px 16px;
}

.agc-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 10px;
}

.agc-message {
  margin: 0 0 6px;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.agc-note {
  margin: 0 0 10px;
  font-size: 12.5px;
  opacity: 0.75;
}

.agc-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.agc-btn {
  padding: 6px 18px;
  border-radius: 7px;
  border: 1px solid rgba(15, 23, 42, 0.18);
  background: var(--surface-2, #f1f5f9);
  font-size: 13.5px;
  cursor: pointer;
}

.agc-btn--ok {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.agc-btn--ok:hover,
.agc-btn--cancel:hover {
  filter: brightness(1.06);
}
</style>
