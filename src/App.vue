<template>
  <AppErrorBoundary>
    <AppShell />
  </AppErrorBoundary>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import AppErrorBoundary from '@/components/AppErrorBoundary.vue'
import AppShell from '@/layouts/AppShell.vue'
import { toastStore } from '@/lib/toast'

// Web-mode transport lifecycle toasts (2026-10-21): the server destroys a
// session's uploads when its WebSocket dies, so after an auto-reconnect the
// user is told WHY an already-uploaded image may have stopped displaying.
// The desktop transport never fires these events.
// Web 模式传输生命周期提示（2026-10-21）：服务器在 WebSocket 断开时销毁该会话
// 的上传文件，自动重连后提示用户「已上传图像可能需要重传」的原因。桌面传输
// 不会触发这些事件。
const onWsClosed = (): void => {
  toastStore.push({
    title: '连接 / Connection',
    message: '与服务器的连接已断开，正在自动重连 / Server connection lost — reconnecting',
    tone: 'warning',
  })
}
const onWsReconnected = (): void => {
  toastStore.push({
    title: '连接 / Connection',
    message: '已重新连接（新会话）——如已上传的图像不再显示，请重新上传 / ' +
      'Reconnected (new session) — re-upload previously uploaded images if they stop displaying',
    tone: 'info',
  })
}
onMounted(() => {
  window.addEventListener('xfais:ws-closed', onWsClosed)
  window.addEventListener('xfais:ws-reconnected', onWsReconnected)
})
onBeforeUnmount(() => {
  window.removeEventListener('xfais:ws-closed', onWsClosed)
  window.removeEventListener('xfais:ws-reconnected', onWsReconnected)
})
</script>
