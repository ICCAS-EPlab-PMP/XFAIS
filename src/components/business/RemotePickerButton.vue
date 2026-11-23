<template>
  <span class="rpb-wrap" :title="buttonTitle">
    <button
      class="rpb-btn"
      :class="{ 'rpb-btn--has-profile': hasProfile, 'rpb-btn--web-disabled': !isDesktop }"
      type="button"
      :disabled="!isDesktop"
      :data-testid="testIds.remotePickerButton"
      @click="open = true"
    >
      ☁ {{ label ?? t('remoteData.picker.button') }}
    </button>
    <RemoteFilePicker
      :mode="mode"
      :extensions="extensions"
      :visible="open"
      @close="open = false"
      @picked="onPicked"
    />
  </span>
</template>

<script setup lang="ts">
/**
 * RemotePickerButton.vue — 「从远端服务器选择」一行式接入按钮
 *
 * 内嵌 RemoteFilePicker 弹窗；未配置远端服务器时点击弹窗会引导去设置页。
 * files 模式 emit picked(paths: string[])；folder 模式 emit pickedFolder(dir)。
 * extensions 客户端过滤远端文件显示（如 ['poni']）。
 * web 模式整体置灰禁用（SFTP 能力仅桌面版），tooltip 说明原因。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import RemoteFilePicker from '@/components/business/RemoteFilePicker.vue'
import { testIds } from '@/lib/testIds'
import { primaryServer } from '@/lib/remoteSftpProfile'
import { useTransport } from '@/lib/transport'

const props = withDefaults(defineProps<{
  mode?: 'files' | 'folder'
  /** 仅允许这些扩展名的远端文件（不含点）；空 = 不过滤。 */
  extensions?: string[]
  label?: string
}>(), {
  mode: 'files',
  extensions: () => [],
  label: undefined
})

const emit = defineEmits<{
  /** files 模式：下载后的本地文件绝对路径列表。 */
  picked: [paths: string[]]
  /** folder 模式：下载后的本地目录绝对路径。 */
  pickedFolder: [dir: string]
}>()

const { t } = useI18n()
const transport = useTransport()
const isDesktop = transport.isDesktop()
const open = ref(false)

const hasProfile = computed(() => {
  const primary = primaryServer()
  return Boolean(primary?.host && primary?.username)
})
const buttonTitle = computed(() =>
  !isDesktop
    ? t('remoteData.desktopOnlyBody')
    : hasProfile.value
      ? t('remoteData.picker.buttonTitle', { host: primaryServer()?.label || primaryServer()?.host || '' })
      : t('remoteData.picker.needSetup')
)

function onPicked(payload: { files: string[]; folder: string | null }): void {
  if (payload.folder !== null) {
    emit('pickedFolder', payload.folder)
  } else {
    emit('picked', payload.files)
  }
}
</script>

<style scoped>
.rpb-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
}

.rpb-btn--has-profile {
  border-color: var(--color-primary, #1e40af);
  color: var(--color-primary, #1e40af);
}

.rpb-btn--web-disabled {
  opacity: 0.45;
}

.rpb-btn:disabled {
  cursor: not-allowed;
}
</style>
