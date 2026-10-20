<script setup lang="ts">
/**
 * Bottom status bar: point counts, fit extent, last-fit summary, hover readout.
 */
import { computed } from 'vue'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useFit } from '@/lib/curvefit/stores/fit'
import { useUi } from '@/lib/curvefit/stores/ui'
import { fmtMs, fmtSig } from '@/lib/curvefit/utils/format'

const sp = useSpectrum()
const pk = usePeaks()
const fit = useFit()
const ui = useUi()

const included = computed(() => sp.meta.n - sp.meta.excluded)

const hoverText = computed(() => {
  const h = ui.hover.value
  if (!h) return ''
  return `x ${fmtSig(h.x, 6)}   y ${fmtSig(h.y, 6)}`
})

const lastFitText = computed(() => {
  const s = fit.lastStats.value
  if (!s) return ''
  return `r² ${Number.isFinite(s.r2) ? s.r2.toFixed(5) : '—'} · ${s.iterations} iter · ${fmtMs(s.timeMs)}`
})
</script>

<template>
  <footer class="status">
    <span class="grp">
      <template v-if="sp.ready.value">
        点 <b class="num">{{ included }}</b> / {{ sp.meta.n }}
        <template v-if="sp.meta.excluded > 0">
          · 排除 <b class="num warn">{{ sp.meta.excluded }}</b>
        </template>
        <template v-if="fit.options.fitExtent > 1"> · fitExtent 1/{{ fit.options.fitExtent }}</template>
      </template>
      <template v-else>无数据</template>
    </span>

    <span class="grp">
      峰 <b class="num">{{ pk.list.value.length }}</b>
      <template v-if="pk.list.value.length > 0">（启用 {{ pk.enabledPeaks.value.length }}）</template>
      · 基线 {{ pk.baseline.enabled ? '开' : '关' }}
    </span>

    <span class="grp mid">
      <template v-if="fit.status.value === 'running'">
        <span class="spinner" />
        拟合中… 第 {{ fit.telemetry.iter }} 迭代
      </template>
      <template v-else-if="lastFitText">{{ lastFitText }}</template>
      <template v-else>就绪</template>
    </span>

    <span class="grp right mono">{{ hoverText }}</span>
  </footer>
</template>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: 18px;
  height: 26px;
  padding: 0 12px;
  background: var(--bg-1);
  border-top: 1px solid var(--border);
  font-size: var(--fs-small);
  color: var(--status-text);
  flex: none;
  user-select: none;
  transition: background-color var(--speed) ease;
}
.grp {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.grp b {
  color: var(--text-1);
  font-weight: 600;
}
.grp b.warn {
  color: var(--warning);
}
.mid {
  margin-left: auto;
}
.right {
  min-width: 220px;
  justify-content: flex-end;
}
.mono {
  font-variant-numeric: tabular-nums;
}
</style>
