<script setup lang="ts">
/** 自动寻峰对话框：残差法 / 二阶导数法 + 灵敏度 + 上限 + 预平滑。 */
import { computed, ref } from 'vue'
import Modal from './Modal.vue'
import AppIcon from './AppIcon.vue'
import type { DetectOptions, DetectedPeak } from '@/lib/pwcore/shared/types'
import type { PeakFnId } from '@/lib/pwcore/shared/registry'
import { detectPeaks } from '@/lib/curvefit/core-bridge/engine'
import { createPeak, usePeaks } from '@/lib/curvefit/stores/peaks'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { FN_GROUPS } from '@/lib/curvefit/stores/peaks'
import { useUi } from '@/lib/curvefit/stores/ui'

const props = defineProps<{ method: 'residual' | 'deriv2' }>()
const emit = defineEmits<{ close: [] }>()

const sp = useSpectrum()
const pk = usePeaks()

const TITLES = {
  residual: '自动寻峰 — 残差法 (残差法)',
  deriv2: '自动寻峰 — 二阶导数法 (残差法I)',
} as const

const sensitivity = ref(0.6)
const maxPeaks = ref(12)
const fn = ref<PeakFnId>(pk.defaultFn.value)
const smoothWindow = ref(0)
const running = ref(false)
const found = ref<DetectedPeak[] | null>(null)

const opts = computed<DetectOptions>(() => ({
  method: props.method,
  sensitivity: Math.min(1, Math.max(0, sensitivity.value)),
  maxPeaks: Math.min(100, Math.max(1, Math.round(maxPeaks.value))),
  fn: fn.value,
  smoothWindow: Math.max(0, Math.round(smoothWindow.value)),
}))

function run(): void {
  const xv = sp.x.value
  const yv = sp.y.value
  if (!xv || !yv) {
    pushToast('warn', '没有数据')
    return
  }
  running.value = true
  try {
    const peaks = detectPeaks(xv, yv, opts.value)
    peaks.sort((a, b) => b.strength - a.strength)
    found.value = peaks.slice(0, opts.value.maxPeaks)
  } catch (err) {
    pushToast('error', `寻峰失败：${err instanceof Error ? err.message : String(err)}`)
  } finally {
    running.value = false
  }
}

function applyAll(): void {
  const list = found.value
  if (!list || list.length === 0) return
  const snap = pk.exportSnapshot()
  const added = list.map((d) => createPeak(fn.value, d.x0, d.y0, Math.max(d.width, 1e-12)))
  const after = pk.exportSnapshot()
  pushCommand({
    label: `自动寻峰 (+${added.length})`,
    undo: () => pk.importSnapshot(snap),
    redo: () => pk.importSnapshot(after),
  })
  pushToast('success', `已自动添加 ${added.length} 个峰`)
  useUi().step.value = 'peaks'
  emit('close')
}
</script>

<template>
  <Modal :title="TITLES[props.method]" :width="400" @close="emit('close')">
    <div class="form">
      <div class="slider-row">
        <span class="k">灵敏度</span>
        <input v-model.number="sensitivity" class="slider" type="range" min="0" max="1" step="0.05" />
        <span class="num val">{{ sensitivity.toFixed(2) }}</span>
      </div>
      <p class="hint">灵敏度越高，检出的峰越多（含弱峰与肩峰）。</p>

      <label class="row">
        <span class="k">峰数上限</span>
        <input v-model.number="maxPeaks" class="field num" inputmode="numeric" />
      </label>

      <label class="row">
        <span class="k">峰函数</span>
        <select v-model="fn" class="select">
          <optgroup v-for="g in FN_GROUPS" :key="g.family" :label="g.label">
            <option v-for="f in g.fns" :key="f.id" :value="f.id">{{ f.name }} — {{ f.label }}</option>
          </optgroup>
        </select>
      </label>

      <label class="row">
        <span class="k">预平滑窗口（0 = 不平滑）</span>
        <input v-model.number="smoothWindow" class="field num" inputmode="numeric" />
      </label>

      <div v-if="found" class="result">
        <AppIcon name="target" :size="14" />
        检出 <b>{{ found.length }}</b> 个候选峰（按强度排序）
      </div>
    </div>
    <template #footer>
      <button class="btn" @click="emit('close')">取消</button>
      <button class="btn" :disabled="!sp.ready.value || running" @click="run">
        <span v-if="running" class="spinner" />
        检测
      </button>
      <button class="btn primary" :disabled="!found || found.length === 0" @click="applyAll">
        <AppIcon name="plus" :size="13" />添加为峰
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.slider-row .k {
  flex: none;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.slider {
  flex: 1;
}
.val {
  min-width: 34px;
  text-align: right;
  color: var(--accent);
  font-weight: 600;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.row .k {
  flex: 1;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.row .field {
  width: 90px;
}
.row .select {
  width: 190px;
}
.result {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 10px;
  background: var(--success-soft);
  border: 1px solid var(--success);
  border-radius: var(--radius-sm);
  color: var(--success);
  font-size: var(--fs-body);
}
</style>
