<template>
  <div class="settings-view">
    <section class="settings-card" data-ai-id="settings:card">
      <header class="settings-card-header">
        <h1>{{ t('settings.title') }}</h1>
        <p>{{ t('settings.subtitle') }}</p>
      </header>

      <!-- Language / 语言 -->
      <div class="settings-section">
        <h2>{{ t('settings.language.title') }}</h2>
        <p class="settings-hint">{{ t('settings.language.hint') }}</p>
        <div class="settings-row">
          <select v-model="localeProxy" class="settings-select" data-testid="settings-locale">
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>

      <!-- Performance / 性能 -->
      <div class="settings-section">
        <h2>{{ t('settings.performance.title') }}</h2>
        <p class="settings-hint">{{ t('settings.performance.hint') }}</p>

        <label class="settings-field">
          <span class="settings-label">{{ t('settings.performance.defaultMethod') }}</span>
          <select v-model="settings.performance.defaultMethod" class="settings-select" data-testid="settings-default-method">
            <option value="splitpixel">splitpixel</option>
            <option value="csr">csr</option>
          </select>
          <small class="settings-hint">{{ t('settings.performance.defaultMethodHint') }}</small>
        </label>

        <label class="settings-field settings-toggle">
          <input
            v-model="settings.performance.batchParallel"
            type="checkbox"
            data-testid="settings-batch-parallel"
          />
          <span class="settings-label">{{ t('settings.performance.batchParallel') }}</span>
          <small class="settings-hint">{{ t('settings.performance.batchParallelHint') }}</small>
        </label>

        <label v-if="settings.performance.batchParallel" class="settings-field">
          <span class="settings-label">{{ t('settings.performance.batchWorkers') }}</span>
          <NumberField
            :model-value="settings.performance.batchWorkers"
            min="1"
            max="16"
            class="settings-input"
            data-testid="settings-batch-workers"
            @update:model-value="(v) => { if (v != null) settings.performance.batchWorkers = v }"
          />
          <small class="settings-hint">{{ t('settings.performance.batchWorkersHint') }}</small>
        </label>

        <label class="settings-field">
          <span class="settings-label">{{ t('settings.performance.ompThreads') }}</span>
          <select v-model="ompProxy" class="settings-select" data-testid="settings-omp-threads">
            <option value="auto">{{ t('settings.performance.ompThreadsAuto') }}</option>
            <option v-for="n in ompChoices" :key="n" :value="String(n)">{{ n }}</option>
          </select>
          <small class="settings-hint">{{ t('settings.performance.ompThreadsHint') }}</small>
        </label>
        <p class="settings-note">{{ t('settings.performance.restartNote') }}</p>
      </div>

      <!-- Remote data sync (SFTP) / 远程数据同步·多服务器 -->
      <div class="settings-section" data-ai-id="settings:remote-sftp">
        <h2>{{ t('settings.remoteSync.title') }}</h2>
        <p class="settings-hint">{{ t('settings.remoteSync.hint') }}</p>
        <!-- web 模式：SFTP 能力仅桌面版，整个分区置灰可见 -->
        <p v-if="!isDesktop" class="settings-web-note" data-testid="settings-remote-web-note">
          {{ t('settings.remoteSync.webDisabledHint') }}
        </p>
        <fieldset :disabled="!isDesktop" class="settings-fieldset">
          <!-- 服务器列表 / server list -->
        <div v-if="profile.servers.length" class="srv-list" data-testid="settings-remote-list">
          <div
            v-for="s in profile.servers"
            :key="s.id"
            class="srv-row"
            :class="{ 'srv-row--primary': s.id === profile.primaryId }"
          >
            <span class="srv-star" :title="s.id === profile.primaryId ? t('settings.remoteSync.primary') : ''">
              {{ s.id === profile.primaryId ? '★' : '☆' }}
            </span>
            <span class="srv-name">
              {{ s.label || s.host }}
              <small class="srv-sub">{{ s.username }}@{{ s.host }}:{{ s.port }}</small>
            </span>
            <button
              v-if="s.id !== profile.primaryId"
              class="settings-btn"
              type="button"
              :data-testid="`settings-remote-primary-${s.id}`"
              @click="makePrimary(s.id)"
            >
              {{ t('settings.remoteSync.makePrimary') }}
            </button>
            <button class="settings-btn" type="button" @click="editServer(s)">{{ t('settings.remoteSync.edit') }}</button>
            <button class="settings-btn settings-btn-danger" type="button" @click="removeServerById(s.id)">
              {{ t('settings.remoteSync.remove') }}
            </button>
          </div>
        </div>
        <p v-else class="settings-hint">{{ t('settings.remoteSync.noServers') }}</p>

        <!-- 添加/编辑表单 / add or edit form -->
        <div class="srv-form">
          <h3 class="srv-form-title">
            {{ editing ? t('settings.remoteSync.editTitle', { host: form.host || '…' }) : t('settings.remoteSync.addTitle') }}
          </h3>

          <label class="settings-field">
            <span class="settings-label">{{ t('settings.remoteSync.label') }}</span>
            <input v-model="form.label" class="settings-input" type="text" :placeholder="t('settings.remoteSync.labelPlaceholder')" />
          </label>

          <label class="settings-field">
            <span class="settings-label">{{ t('remoteData.host') }}</span>
            <input
              v-model="form.host"
              class="settings-input"
              type="text"
              data-testid="settings-remote-host"
              :placeholder="t('remoteData.host')"
            />
          </label>

          <div class="srv-two">
            <label class="settings-field">
              <span class="settings-label">{{ t('remoteData.port') }}</span>
              <input
                v-model.number="form.port"
                class="settings-input"
                type="number"
                min="1"
                max="65535"
                data-testid="settings-remote-port"
              />
            </label>
            <label class="settings-field">
              <span class="settings-label">{{ t('remoteData.username') }}</span>
              <input
                v-model="form.username"
                class="settings-input"
                type="text"
                data-testid="settings-remote-username"
              />
            </label>
          </div>

          <label class="settings-field">
            <span class="settings-label">{{ t('remoteData.authMode') }}</span>
            <select v-model="form.authMode" class="settings-select" data-testid="settings-remote-auth">
              <option value="password">{{ t('remoteData.authByPassphrase') }}</option>
              <option value="key">{{ t('remoteData.authKey') }}</option>
            </select>
          </label>

          <label v-if="form.authMode === 'password'" class="settings-field">
            <span class="settings-label">{{ t('remoteData.passphrase') }}</span>
            <input
              v-model="form.passphrase"
              class="settings-input"
              type="password"
              autocomplete="off"
              :placeholder="t('settings.remoteSync.passphrasePlaceholder')"
            />
          </label>

          <template v-else>
            <label class="settings-field">
              <span class="settings-label">{{ t('remoteData.keyPath') }}</span>
              <input v-model="form.keyPath" class="settings-input" type="text" />
            </label>
            <label class="settings-field">
              <span class="settings-label">{{ t('remoteData.keyPassphrase') }}</span>
              <input v-model="form.keyPassphrase" class="settings-input" type="password" autocomplete="off" />
            </label>
          </template>

          <label class="settings-field settings-toggle">
            <input v-model="form.remember" type="checkbox" data-testid="settings-remote-remember" />
            <span class="settings-label">{{ t('remoteData.rememberPassphrase') }}</span>
            <small class="settings-hint">{{ t('settings.remoteSync.rememberHint') }}</small>
          </label>

          <div class="settings-row">
            <button class="settings-btn" type="button" data-testid="settings-remote-save" @click="saveServer">
              {{ t('settings.remoteSync.save') }}
            </button>
            <button
              v-if="editing"
              class="settings-btn"
              type="button"
              @click="startAdd"
            >
              {{ t('settings.remoteSync.cancelEdit') }}
            </button>
            <button
              class="settings-btn settings-btn-primary"
              type="button"
              data-testid="settings-remote-test"
              :disabled="remoteTesting"
              @click="testRemoteConnection"
            >
              {{ remoteTesting ? t('remoteData.connecting') : t('settings.remoteSync.test') }}
            </button>
            <button
              v-if="editing && form.hostFingerprint"
              class="settings-btn"
              type="button"
              @click="clearEditingFingerprint"
            >
              {{ t('remoteData.clearFingerprint') }}
            </button>
          </div>

          <p v-if="remoteTestResult" class="settings-hint" :class="{ 'settings-error': !remoteTestOk }">
            {{ remoteTestResult }}
          </p>
          <p v-if="editing && form.hostFingerprint" class="settings-hint">
            {{ t('settings.remoteSync.fingerprint', { fp: form.hostFingerprint }) }}
          </p>
        </div>

        <!-- 缓存池（下载无损压缩暂存）/ compressed download cache pool -->
        <div class="srv-cache" data-testid="settings-cache-pool">
          <h3 class="srv-cache-title">{{ t('settings.remoteSync.cache.title') }}</h3>
          <label class="srv-cache-field srv-cache-field--row">
            <input
              v-model="settings.remoteSync.cache.compress"
              type="checkbox"
              data-testid="settings-cache-compress"
            />
            <span>{{ t('settings.remoteSync.cache.compress') }}</span>
          </label>
          <small class="settings-hint">{{ t('settings.remoteSync.cache.compressHint') }}</small>
          <label class="srv-cache-field">
            <span>{{ t('settings.remoteSync.cache.ttl') }}</span>
            <NumberField
              v-model="settings.remoteSync.cache.ttlMinutes"
              :min="1"
              :step="60"
              class="srv-cache-input"
              data-testid="settings-cache-ttl"
            />
            <small class="settings-hint">{{ t('settings.remoteSync.cache.ttlHint') }}</small>
          </label>
          <label class="srv-cache-field">
            <span>{{ t('settings.remoteSync.cache.dir') }}</span>
            <input
              v-model="settings.remoteSync.cache.dir"
              type="text"
              class="srv-cache-input srv-cache-input--mono"
              :placeholder="t('settings.remoteSync.cache.dirPlaceholder')"
              data-testid="settings-cache-dir"
            />
            <small class="settings-hint">{{ t('settings.remoteSync.cache.dirHint') }}</small>
          </label>
        </div>

        <p class="settings-note">{{ t('remoteData.connectionSectionHint') }}</p>
        </fieldset>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * SettingsView.vue — 应用设置页
 * Language / performance (default method, batch parallelism, OpenMP).
 * All changes persist immediately via useSettings().
 * 语言 / 性能（默认算法、批处理并行、OpenMP）。所有修改经 useSettings() 即时持久化。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/lib/settings'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import NumberField from '@/components/common/NumberField.vue'
import {
  createEmptyServer,
  deleteRememberedPassword,
  loadLegacyRememberedPassword,
  loadRememberedPassword,
  removeServer,
  saveRememberedPassword,
  setPrimaryServer,
  updateServer,
  upsertServer,
  useRemoteSftpProfile,
  type RemoteSftpServer
} from '@/lib/remoteSftpProfile'
import { useRemoteSftpSession } from '@/lib/remoteSftpSession'

const { t, locale } = useI18n()
const toast = useToast()
const settings = useSettings()
const transport = useTransport()
/** web 模式：远程数据同步（SFTP）仅桌面版，分区置灰可见。 */
const isDesktop = transport.isDesktop()

// ── 远程数据同步·多服务器 / remote SFTP servers ────────────────────────────
const profile = useRemoteSftpProfile()
const remoteSession = useRemoteSftpSession()

interface ServerForm {
  id: string
  label: string
  host: string
  port: number
  username: string
  authMode: 'password' | 'key'
  keyPath: string
  hostFingerprint: string
  remember: boolean
  passphrase: string
  keyPassphrase: string
}

function blankForm(): ServerForm {
  const s = createEmptyServer()
  return {
    id: s.id,
    label: '',
    host: '',
    port: 22,
    username: '',
    authMode: 'password',
    keyPath: '',
    hostFingerprint: '',
    remember: false,
    passphrase: '',
    keyPassphrase: ''
  }
}

const form = reactive<ServerForm>(blankForm())
/** 正在编辑的服务器 id；null = 添加新模式。 */
const editingId = ref<string | null>(null)
const editing = computed(() => editingId.value !== null)
const remoteTesting = ref(false)
const remoteTestResult = ref('')
const remoteTestOk = ref(false)

onMounted(async () => {
  // 旧单档案口令一次性迁移到首个服务器 / one-time legacy secret migration
  const first = profile.servers[0]
  if (first?.rememberPassphrase) {
    const existing = await loadRememberedPassword(first.id)
    if (existing === null) {
      const legacy = await loadLegacyRememberedPassword()
      if (legacy) await saveRememberedPassword(first.id, legacy)
    }
  }
})

function startAdd(): void {
  Object.assign(form, blankForm())
  editingId.value = null
  remoteTestResult.value = ''
}

async function editServer(server: RemoteSftpServer): Promise<void> {
  Object.assign(form, {
    ...server,
    remember: server.rememberPassphrase,
    passphrase: '',
    keyPassphrase: ''
  })
  editingId.value = server.id
  remoteTestResult.value = ''
  if (server.rememberPassphrase) {
    const remembered = await loadRememberedPassword(server.id)
    if (remembered) form.passphrase = remembered
  }
}

async function saveServer(): Promise<string> {
  const editingNow = editing.value
  const previous = editingNow ? profile.servers.find(s => s.id === editingId.value) : null
  const hostChanged = previous ? form.host.trim() !== previous.host : true
  const server: RemoteSftpServer = {
    id: editingNow && editingId.value ? editingId.value : form.id,
    label: form.label.trim() || form.host.trim(),
    host: form.host.trim(),
    port: Number(form.port) || 22,
    username: form.username.trim(),
    authMode: form.authMode,
    keyPath: form.authMode === 'key' ? form.keyPath.trim() : '',
    remoteDir: previous?.remoteDir ?? '',
    localDir: previous?.localDir ?? '',
    rememberPassphrase: form.remember,
    // 仅当主机变化时清除旧指纹（换服务器需重新 TOFU）
    hostFingerprint: hostChanged ? '' : (previous?.hostFingerprint ?? '')
  }
  upsertServer(server)
  editingId.value = server.id
  if (form.remember && form.authMode === 'password' && form.passphrase) {
    const ok = await saveRememberedPassword(server.id, form.passphrase)
    if (!ok) {
      toast.push({ title: t('settings.remoteSync.title'), message: t('remoteData.rememberUnavailable'), tone: 'warning' })
    }
  } else if (!form.remember) {
    await deleteRememberedPassword(server.id)
  }
  form.hostFingerprint = server.hostFingerprint
  remoteTestResult.value = ''
  toast.push({ title: t('settings.remoteSync.title'), message: t('settings.remoteSync.saved'), tone: 'success' })
  return server.id
}

function makePrimary(id: string): void {
  setPrimaryServer(id)
  toast.push({ title: t('settings.remoteSync.title'), message: t('settings.remoteSync.primarySet'), tone: 'success' })
}

async function removeServerById(id: string): Promise<void> {
  await deleteRememberedPassword(id)
  removeServer(id)
  if (editingId.value === id) startAdd()
  remoteTestResult.value = ''
}

function clearEditingFingerprint(): void {
  if (editingId.value) {
    updateServer(editingId.value, { hostFingerprint: '' })
    form.hostFingerprint = ''
    remoteTestResult.value = ''
    toast.push({ title: t('settings.remoteSync.title'), message: t('remoteData.clearFingerprint') + ' ✓', tone: 'info' })
  }
}

async function testRemoteConnection(): Promise<void> {
  if (!form.host.trim() || !form.username.trim()) {
    remoteTestOk.value = false
    remoteTestResult.value = t('settings.remoteSync.needHost')
    return
  }
  remoteTesting.value = true
  remoteTestResult.value = ''
  try {
    // 先保存档案再测试（含口令），成功回填指纹（TOFU）
    const serverId = await saveServer()
    const err = await remoteSession.connect(serverId, {
      passphrase: form.passphrase,
      keyPassphrase: form.keyPassphrase
    })
    if (err) {
      remoteTestOk.value = false
      const mismatch = err.includes('不匹配') || err.toLowerCase().includes('mismatch')
      remoteTestResult.value = mismatch ? t('remoteData.fingerprintChanged') : err
      return
    }
    updateServer(serverId, { hostFingerprint: remoteSession.fingerprint.value })
    form.hostFingerprint = remoteSession.fingerprint.value || ''
    remoteTestOk.value = true
    remoteTestResult.value = t('settings.remoteSync.testOk', { host: form.host.trim() })
    await remoteSession.disconnect()
  } finally {
    remoteTesting.value = false
  }
}

const ompChoices = [2, 4, 8, 12, 16, 24, 32]

const localeProxy = computed<'zh' | 'en'>({
  get: () => (locale.value === 'en' ? 'en' : 'zh'),
  set: (value) => {
    locale.value = value
    settings.locale = value
    toast.push({ title: t('settings.title'), message: t('settings.performance.saved'), tone: 'success' })
  }
})

const ompProxy = computed<string>({
  get: () => (settings.performance.ompThreads === 'auto' ? 'auto' : String(settings.performance.ompThreads)),
  set: (value) => {
    settings.performance.ompThreads = value === 'auto' ? 'auto' : Number(value)
  }
})
</script>

<style scoped>
.settings-view {
  display: flex;
  justify-content: center;
  padding: 8px 0 32px;
}

.settings-card {
  width: min(720px, 100%);
  padding: 28px 32px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  display: grid;
  gap: 28px;
}

.settings-card-header h1 {
  margin: 0 0 6px;
  font-size: 1.5rem;
}

.settings-card-header p {
  margin: 0;
  color: var(--text-secondary);
}

.settings-section {
  display: grid;
  gap: 12px;
  padding-top: 18px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.settings-section h2 {
  margin: 0;
  font-size: 1.1rem;
}

.settings-hint {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.settings-note {
  color: var(--text-secondary);
  font-size: 0.82rem;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 12px;
  padding: 8px 12px;
}

.settings-field {
  display: grid;
  gap: 6px;
}

.settings-label {
  font-weight: 600;
  font-size: 0.92rem;
}

.settings-select,
.settings-input {
  width: 100%;
  max-width: 360px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.92);
  font-size: 0.92rem;
}

.settings-toggle {
  grid-template-columns: auto 1fr;
  align-items: baseline;
}

.settings-toggle input {
  width: 16px;
  height: 16px;
  grid-row: span 2;
}

.settings-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.settings-btn {
  padding: 8px 16px;
  border-radius: 12px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.92);
  font-size: 0.9rem;
  cursor: pointer;
}

.settings-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-btn-primary {
  background: var(--color-primary, #1e40af);
  border-color: var(--color-primary, #1e40af);
  color: #fff;
}

.settings-error {
  color: #b91c1c;
}

/* Multi-server list / 多服务器列表 */
.srv-list {
  display: grid;
  gap: 6px;
}

.srv-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 12px;
  flex-wrap: wrap;
}

.srv-row--primary {
  border-color: var(--color-primary, #1e40af);
  background: rgba(30, 64, 175, 0.05);
}

.srv-star {
  font-size: 1.1rem;
  color: var(--color-primary, #1e40af);
}

.srv-name {
  font-weight: 600;
  font-size: 0.92rem;
  margin-right: auto;
}

.srv-sub {
  font-weight: 400;
  opacity: 0.65;
  margin-left: 6px;
}

.srv-form {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px dashed rgba(203, 213, 225, 0.9);
  border-radius: 12px;
}

.srv-form-title {
  margin: 0;
  font-size: 0.98rem;
}

.srv-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.settings-btn-danger {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.4);
}

/* web 模式置灰：远程数据同步分区可见但不可操作 */
.settings-fieldset {
  border: none;
  padding: 0;
  margin: 0;
  min-inline-size: auto;
}

.settings-fieldset:disabled {
  opacity: 0.5;
}

.settings-fieldset:disabled button {
  cursor: not-allowed;
}

.settings-web-note {
  font-size: 12.5px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(234, 179, 8, 0.12);
  margin: 0 0 8px;
}

/* 缓存池（下载无损压缩暂存）设置块 */
.srv-cache {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border, #e2e8f0);
}

.srv-cache-title {
  margin: 0 0 8px;
  font-size: 14px;
}

.srv-cache-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 8px 0;
  font-size: 13px;
}

.srv-cache-field--row {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.srv-cache-input {
  max-width: 320px;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  font-size: 13px;
}

.srv-cache-input--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
</style>
