<script setup lang="ts">
/** 平滑对话框：SG / 移动平均 / FFT 低通 + 参数 + 应用（可撤销）。 */
import { computed, ref } from 'vue'
import Modal from './Modal.vue'
import type { SmoothMethod, SmoothOptions } from '@/lib/pwcore/shared/types'
import { smoothData } from '@/lib/curvefit/core-bridge/engine'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { revokeCurves } from '@/lib/curvefit/stores/fit'
import { clearResults } from '@/lib/curvefit/stores/peaks'

const props = defineProps<{ method: SmoothMethod }>()
const emit = defineEmits<{ close: [] }>()

const sp = useSpectrum()

const TITLES: Record<SmoothMethod, string> = {
  sg: 'Savitzky-Golay 平滑',
  movavg: '移动平均平滑',
  fftLowpass: 'FFT 低通滤波',
}

const window_ = ref(11)
const polyOrder = ref(3)
const cutoff = ref(0.2)

const options = computed<SmoothOptions>(() => ({
  method: props.method,
  window: Math.max(3, Math.round(window_.value) | 1),
  polyOrder: Math.min(6, Math.max(2, Math.round(polyOrder.value))),
  cutoff: Math.min(1, Math.max(0.01, cutoff.value)),
}))

function apply(): void {
  const yv = sp.y.value
  if (!yv) {
    pushToast('warn', '没有数据')
    emit('close')
    return
  }
  let ny: Float64Array
  try {
    ny = smoothData(yv, options.value)
  } catch (err) {
    pushToast('error', `平滑失败：${err instanceof Error ? err.message : String(err)}`)
    return
  }
  if (ny.length !== yv.length) {
    pushToast('error', '平滑返回长度与数据不一致，已放弃')
    return
  }
  const old = sp.replaceY(ny)
  // 数据变更使既有拟合结果失效
  revokeCurves()
  clearResults()
  if (old) {
    pushCommand({
      label: TITLES[props.method],
      undo: () => {
        sp.restoreY(old)
        revokeCurves()
        clearResults()
      },
      redo: () => {
        sp.restoreY(ny)
        revokeCurves()
        clearResults()
      },
    })
  }
  pushToast('success', `${TITLES[props.method]} 已应用（Ctrl+Z 可撤销）`)
  emit('close')
}
</script>

<template>
  <Modal :title="TITLES[props.method]" :width="380" @close="emit('close')">
    <div class="form">
      <p class="hint">
        平滑作用于当前数据列并生成新数据（原列保留在撤销栈中）；拟合输入随之更新。
      </p>

      <template v-if="props.method === 'sg'">
        <label class="row">
          <span class="k">窗口点数（奇数）</span>
          <input v-model.number="window_" class="field num" inputmode="numeric" />
        </label>
        <label class="row">
          <span class="k">多项式阶数 2–6</span>
          <input v-model.number="polyOrder" class="field num" inputmode="numeric" />
        </label>
      </template>

      <template v-else-if="props.method === 'movavg'">
        <label class="row">
          <span class="k">窗口点数</span>
          <input v-model.number="window_" class="field num" inputmode="numeric" />
        </label>
      </template>

      <template v-else>
        <label class="row">
          <span class="k">截止频率（Nyquist 比例 0–1）</span>
          <input v-model.number="cutoff" class="field num" inputmode="decimal" />
        </label>
      </template>

      <div class="preview-hint hint">
        当前参数：{{ options.method === 'fftLowpass' ? `cutoff = ${options.cutoff}` : `window = ${options.window}` }}{{ options.method === 'sg' ? `, poly = ${options.polyOrder}` : '' }}
      </div>
    </div>
    <template #footer>
      <button class="btn" @click="emit('close')">取消</button>
      <button class="btn primary" :disabled="!sp.ready.value" @click="apply">应用</button>
    </template>
  </Modal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.preview-hint {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
}
</style>
