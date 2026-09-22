<template>
  <div v-if="mode === 'openFolder' && !transport.isDesktop()" class="file-dialog-button">
    <!-- Folder selection unavailable in Web mode -->
    <label class="fd-label">{{ label ?? t('business.fileDialog.chooseFolder') }}</label>
    <div class="fd-row">
      <span class="fd-placeholder">{{ t('business.fileDialog.noSelection') }}</span>
    </div>
  </div>
  <div
    v-else
    :data-testid="testIds.fileDialogButton"
    class="file-dialog-button"
    :class="{ 'file-dialog-button--drop': dropZone.isDragging.value }"
    @dragenter="dropZone.onDragEnter"
    @dragover="dropZone.onDragOver"
    @dragleave="dropZone.onDragLeave"
    @drop="dropZone.onDrop"
  >
    <label class="fd-label">{{ label ?? t('business.fileDialog.chooseFile') }}</label>
    <div class="fd-row">
      <button
        type="button"
        class="fd-trigger"
        :data-testid="testIds.fileDialogTrigger"
        @click="handleOpen"
      >
        {{ buttonText }}
      </button>
      <span
        v-if="modelValue"
        class="fd-path"
        :data-testid="testIds.fileDialogPath"
        :title="modelValue"
      >
        {{ displayName }}
      </span>
      <span v-else-if="dropZone.isDragging.value" class="fd-placeholder fd-placeholder--drop">
        {{ t('business.fileDialog.dropHint') }}
      </span>
      <span v-else class="fd-placeholder">{{ placeholder ?? t('business.fileDialog.noSelection') }}</span>
      <button
        v-if="modelValue"
        type="button"
        class="fd-clear"
        :data-testid="testIds.fileDialogClear"
        @click="handleClear"
      >
        ✕
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * FileDialogButton.vue — 文件/文件夹选择按钮，通过 transport 层支持 Electron 和 Web 模式
 * File/folder selection button via transport layer (Electron + Web).
 * Also acts as a drop target: drag a file/folder onto it to fill in the path.
 * 同时支持拖放：将文件/文件夹拖到组件上即可填入路径。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'
import { useToast } from '@/lib/toast'
import { extensionsFromFilters, shortenNames, useDropZone } from '@/lib/fileDrop'

export type FileDialogMode = 'openFile' | 'saveFile' | 'openFolder'

const props = withDefaults(defineProps<{
  /** Dialog mode: openFile, saveFile, or openFolder / 对话框模式 */
  mode?: FileDialogMode
  /** Button label text / 按钮标签 */
  label?: string
  /** Placeholder when no path selected / 无路径时的占位文本 */
  placeholder?: string
  /** Currently selected path (v-model) / 当前选中路径 */
  modelValue?: string | null
  /** File filters for open/save dialogs / 文件过滤器 */
  filters?: Array<{ name: string; extensions: string[] }>
}>(), {
  mode: 'openFile',
  modelValue: null,
  label: '',
  placeholder: '',
  filters: () => [],
})

const emit = defineEmits<{
  'update:modelValue': [path: string | null]
}>()

const { t } = useI18n()
const transport = useTransport()
const toast = useToast()

const buttonText = computed(() => {
  switch (props.mode) {
    case 'openFile':
      return t('business.fileDialog.chooseFile')
    case 'saveFile':
      return t('business.fileDialog.saveFile')
    case 'openFolder':
      return t('business.fileDialog.chooseFolder')
    default:
      return t('business.fileDialog.chooseFile')
  }
})

const displayName = computed(() => {
  if (!props.modelValue) return ''
  const sep = props.modelValue.includes('/') ? '/' : '\\'
  const parts = props.modelValue.split(sep)
  return parts[parts.length - 1] || props.modelValue
})

/** Normalize selectFiles result (string | string[] | null) to single path or null */
function toSinglePath(result: string | string[] | null): string | null {
  if (result == null) return null
  if (Array.isArray(result)) return result[0] ?? null
  return result
}

async function handleOpen(): Promise<void> {
  let result: string | null = null
  const filterOpts = props.filters ? { filters: props.filters } : undefined

  try {
    switch (props.mode) {
      case 'openFile':
        result = toSinglePath(await transport.selectFiles(filterOpts))
        break
      case 'saveFile':
        result = await transport.selectSavePath(filterOpts)
        break
      case 'openFolder':
        result = await transport.selectFolder()
        break
    }

    if (result !== null) {
      emit('update:modelValue', result)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    toast.push({ title: t('business.fileDialog.uploadFailed'), message, tone: 'error' })
  }
}

// Drag-and-drop: openFile accepts a dropped file, openFolder a dropped folder.
// saveFile keeps click-only behavior (drop there would be ambiguous).
const dropZone = useDropZone({
  transport,
  extensions: () => extensionsFromFilters(props.filters),
  onDrop(resolution) {
    if (props.mode === 'openFolder') {
      if (resolution.folderPath) {
        emit('update:modelValue', resolution.folderPath)
        if (resolution.folderCount > 1) {
          toast.push({
            title: t('business.fileDialog.chooseFolder'),
            message: t('business.fileSelection.dropIgnoredFolders', { count: resolution.folderCount - 1 }),
            tone: 'info',
          })
        }
        return
      }
      if (resolution.folderCount > 0) {
        toast.push({
          title: t('business.fileDialog.chooseFolder'),
          message: t('business.fileDialog.dropFolderWebUnsupported'),
          tone: 'error',
        })
        return
      }
      toast.push({
        title: t('business.fileDialog.chooseFolder'),
        message: t('business.fileDialog.dropOnlyFolder'),
        tone: 'error',
      })
      return
    }

    if (resolution.filePaths.length > 0) {
      emit('update:modelValue', resolution.filePaths[0])
      return
    }
    if (resolution.rejectedNames.length > 0) {
      toast.push({
        title: t('business.fileDialog.chooseFile'),
        message: t('business.fileDialog.dropTypeMismatch', {
          names: shortenNames(resolution.rejectedNames),
        }),
        tone: 'error',
      })
      return
    }
    toast.push({
      title: t('business.fileDialog.chooseFile'),
      message: t('business.fileDialog.dropOnlyFile'),
      tone: 'error',
    })
  },
})

function handleClear(): void {
  emit('update:modelValue', null)
}
</script>

<style scoped>
.file-dialog-button {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-radius: var(--radius-md);
  padding: 2px;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.file-dialog-button--drop {
  background: var(--primary-bg);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.fd-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.fd-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fd-trigger {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.fd-trigger:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.fd-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fd-placeholder {
  flex: 1;
  font-size: 0.8125rem;
  color: var(--text-muted);
  font-style: italic;
}

.fd-placeholder--drop {
  color: var(--primary);
  font-weight: 600;
}

.fd-clear {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.875rem;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.fd-clear:hover {
  color: var(--error);
}
</style>
