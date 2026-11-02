<template>
  <div class="calib-com-panel" data-ai-id="calibration:com-panel">
    <h4 class="ccp-title">{{ t('calibration.com.title') }}</h4>
    <p class="ccp-hint">{{ t('calibration.com.hint') }}</p>

    <!-- Region shape switch: rectangle drag vs polygon vertices. Arming one
         mode disarms the other; clicking the active button disarms. / 区域形状
         开关：拖矩形 vs 点多折框。武装一种即解除另一种；点击己方按钮解除。 -->
    <div class="ccp-row">
      <button
        type="button"
        class="ccp-btn"
        :class="{ 'ccp-btn--armed': comMode === 'rect' }"
        :disabled="busy"
        data-ai-id="calibration:com-rect"
        @click="$emit('update:comMode', comMode === 'rect' ? null : 'rect')"
      >
        {{ t('calibration.com.rect') }}
      </button>
      <button
        type="button"
        class="ccp-btn"
        :class="{ 'ccp-btn--armed': comMode === 'poly' }"
        :disabled="busy"
        data-ai-id="calibration:com-poly"
        @click="$emit('update:comMode', comMode === 'poly' ? null : 'poly')"
      >
        {{ t('calibration.com.poly') }}
      </button>
      <button
        v-if="center"
        type="button"
        class="ccp-btn ccp-btn--clear"
        :disabled="busy"
        data-ai-id="calibration:com-clear"
        @click="$emit('clear-com')"
      >
        {{ t('calibration.com.clear') }}
      </button>
    </div>

    <p class="ccp-hint ccp-hint--mode">
      {{
        comMode === 'rect' ? t('calibration.com.hintRect')
          : comMode === 'poly' ? t('calibration.com.hintPoly')
            : t('calibration.com.hintIdle')
      }}
    </p>

    <p v-if="busy" class="ccp-busy">{{ t('calibration.com.running') }}</p>

    <!-- Confirmed centroid (sub-pixel, canvas pixel coordinates). / 已确认质心
         （亚像素，画布像素坐标）。 -->
    <div v-if="center" class="ccp-result" data-ai-id="calibration:com-result">
      <span class="ccp-result-label">{{ t('calibration.com.result') }}</span>
      <span class="ccp-result-value">
        ({{ center.x.toFixed(2) }}, {{ center.y.toFixed(2) }})
      </span>
    </div>
    <p v-else class="ccp-hint ccp-hint--empty">{{ t('calibration.com.empty') }}</p>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibComPanel.vue — 直通光定心（第三种标定模式）步骤面板
 *
 * Third calibration mode, step 2: the user boxes the DIRECT-BEAM spot on the
 * first uploaded image (rectangle drag or polygon vertices); the backend returns
 * its intensity-weighted centre of mass, which becomes the beam centre every
 * later step uses. This panel owns only the controls + readout — the region
 * drawing itself lives in CalibCanvas (regionMode / comRegion / comCenter).
 * 第三种标定模式的第 2 步：用户在第一张（直通光）图上框出光斑（拖矩形或多折框
 * 顶点），后端返回强度加权质心作为后续所有步骤的光束中心。本面板只负责控件与
 * 读数——区域绘制由 CalibCanvas 承担。
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  /** Armed region shape (null = nothing armed). / 已武装的区域形状。 */
  comMode: 'rect' | 'poly' | null
  /** Confirmed centroid in image pixels (null = none yet). / 已确认质心。 */
  center: { y: number; x: number } | null
  /** beam_center_com request in flight. / 质心请求进行中。 */
  busy: boolean
}>()

defineEmits<{
  'update:comMode': [mode: 'rect' | 'poly' | null]
  'clear-com': []
}>()
</script>

<style scoped>
.calib-com-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ccp-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.ccp-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.ccp-hint--mode {
  color: var(--text-secondary);
}

.ccp-hint--empty {
  font-style: italic;
}

.ccp-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ccp-btn {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 6px 14px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.ccp-btn:hover:not(:disabled) {
  background: var(--bg-hover, rgba(59, 130, 246, 0.08));
}

.ccp-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ccp-btn--armed {
  border-color: #0891b2;
  color: #0e7490;
  background: rgba(34, 211, 238, 0.16);
}

.ccp-btn--clear {
  font-size: 0.72rem;
  padding: 4px 10px;
}

.ccp-busy {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.ccp-result {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid rgba(34, 211, 238, 0.45);
  border-radius: var(--radius-sm);
  background: rgba(34, 211, 238, 0.08);
}

.ccp-result-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.ccp-result-value {
  font-size: 0.85rem;
  font-weight: 600;
  font-family: var(--font-mono);
  color: #0e7490;
}
</style>
