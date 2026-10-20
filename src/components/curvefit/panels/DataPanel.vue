<script setup lang="ts">
/** 数据页：文件信息、点数、范围、权重、排除点管理、显示偏好。 */
import { computed, ref } from 'vue'
import AppIcon from '../AppIcon.vue'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { useUi } from '@/lib/curvefit/stores/ui'
import { useFit } from '@/lib/curvefit/stores/fit'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { importFromText } from '@/lib/curvefit/stores/session'
import { fmtSig } from '@/lib/curvefit/utils/format'

const sp = useSpectrum()
const ui = useUi()
const fit = useFit()

const xRange = computed(() => (sp.ready.value ? `${fmtSig(sp.meta.xMin, 6)} … ${fmtSig(sp.meta.xMax, 6)}` : '—'))
const yRange = computed(() => (sp.ready.value ? `${fmtSig(sp.meta.yMin, 6)} … ${fmtSig(sp.meta.yMax, 6)}` : '—'))

// -- paste intake -----------------------------------------------------------
const pasteText = ref('')

function onParse(): void {
  const text = pasteText.value.trim()
  if (!text) return
  const before = sp.dataVersion.value
  importFromText(text)
  // A successful import bumps dataVersion; keep the text on parse failure.
  if (sp.dataVersion.value !== before) pasteText.value = ''
}

function restoreAll(): void {
  const m = sp.mask.value
  if (!m || sp.meta.excluded === 0) return
  const total = sp.meta.n
  const snap = m.slice()
  sp.restoreAllPoints()
  // Undo/redo rewrite the whole mask: applyMaskSnapshot recomputes
  // meta.excluded and bumps the mask/edit counters.
  // 撤销/重做整体回写掩膜：applyMaskSnapshot 会重算排除计数并刷新计数器。
  pushCommand({
    label: '恢复全部数据',
    undo: () => sp.applyMaskSnapshot(snap),
    redo: () => sp.restoreAllPoints(),
  })
  pushToast('success', `已恢复全部 ${total} 个点`)
}
</script>

<template>
  <div class="panel">
    <div class="panel-title"><AppIcon name="data" :size="13" />数据</div>
    <div class="content">
      <div class="sec-label">粘贴数据</div>
      <div class="paste">
        <textarea
          v-model="pasteText"
          class="field paste-area"
          rows="4"
          spellcheck="false"
          placeholder="每行两个数 x y，逗号/空格/制表符分隔"
        />
        <div class="row-btns">
          <button class="btn sm" :disabled="!pasteText.trim()" @click="onParse">
            <AppIcon name="data" :size="13" />解析
          </button>
        </div>
      </div>

      <div class="kv"><span class="k">名称</span><span class="v" :title="sp.meta.title">{{ sp.meta.title || '—' }}</span></div>
      <div class="kv"><span class="k">来源</span><span class="v">{{ sp.meta.source || '—' }}</span></div>
      <div class="kv"><span class="k">点数</span><span class="v num">{{ sp.meta.n }}</span></div>
      <div class="kv"><span class="k">X 范围</span><span class="v num">{{ xRange }}</span></div>
      <div class="kv"><span class="k">Y 范围</span><span class="v num">{{ yRange }}</span></div>
      <div class="kv"><span class="k">权重列 W</span><span class="v">{{ sp.meta.hasW ? '有' : '无' }}</span></div>
      <div class="kv">
        <span class="k">排除点</span>
        <span class="v num" :class="{ warn: sp.meta.excluded > 0 }">{{ sp.meta.excluded }}</span>
      </div>

      <!-- 排除点从曲线中隐去（各步骤均断开），× 标记只在「数据」步显示；
           本卡片是唯一的恢复入口（用户 2026-10-20 要求）。 -->
      <div v-if="sp.meta.excluded > 0" class="excl-notice">
        <div class="excl-text">
          已排除 {{ sp.meta.excluded }} 点：右拖继续排除 · 左拖恢复 · 或一键恢复全部
        </div>
        <p class="excl-sub">排除点在各步骤的曲线上都不显示；要恢复只能回到「数据」步操作。</p>
        <button class="btn primary sm" @click="restoreAll">
          <AppIcon name="restore2" :size="13" />恢复全部数据
        </button>
      </div>

      <div class="sec-label">显示</div>
      <label class="checkbox">
        <input v-model="ui.showPoints.value" type="checkbox" />
        <span class="box"><AppIcon name="check" :size="10" /></span>
        显示数据点标记（小数据集）
      </label>

      <div class="sec-label">拟合窗口</div>
      <div class="kv">
        <span class="k">fitExtent</span>
        <span class="v">每 {{ fit.options.fitExtent }} 点取 1 参与拟合</span>
      </div>
      <p class="hint body">排除点不参与拟合，并从曲线上隐去；fitExtent 只影响拟合输入。</p>
    </div>
  </div>
</template>

<style scoped>
.content {
  padding: 2px 12px 12px;
}
.warn {
  color: var(--warning);
}
/* Exclusion/fitExtent semantics is body copy, not a caption: --text-2. */
.hint.body {
  color: var(--text-2);
}
.row-btns {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
/* Exclusion gate notice: warning-tinted card with the one-click restore. /
   排除点门禁提示：警示色卡片 + 一键恢复按钮。 */
.excl-notice {
  margin: 8px 0;
  padding: 9px 10px;
  border: 1px solid var(--warning);
  border-radius: var(--radius);
  background: var(--warning-soft);
}
.excl-text {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.45;
}
.excl-sub {
  margin: 4px 0 8px;
  font-size: var(--fs-small);
  color: var(--text-2);
  line-height: 1.4;
}
.excl-notice .btn {
  width: 100%;
  justify-content: center;
}
.checkbox {
  margin: 2px 0;
}
.paste {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.paste .paste-area {
  width: 100%;
  height: auto;
  min-height: 76px;
  padding: 6px 8px;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.45;
  resize: vertical;
}
</style>
