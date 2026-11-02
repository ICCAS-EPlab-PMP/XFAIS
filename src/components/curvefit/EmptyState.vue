<script setup lang="ts">
/** Empty-state card shown when no dataset is loaded. */
import AppIcon from './AppIcon.vue'

const emit = defineEmits<{ import: []; demo: [] }>()
</script>

<template>
  <div class="empty">
    <div class="card panel">
      <div class="glyph">
        <AppIcon name="logo" :size="44" />
      </div>
      <h2>PeakWorkbench 谱峰工作台</h2>
      <p class="hint">
        导入色谱 / 光谱数据（PRN、CSV、TXT），或先加载示例数据体验<br />
        基线 → 放峰 → 拟合 → 报告 的完整工作流。
      </p>
      <div class="actions">
        <button class="btn primary" @click="emit('import')">
          <AppIcon name="import" :size="15" />
          导入数据
        </button>
        <button class="btn" @click="emit('demo')">
          <AppIcon name="flask" :size="15" />
          加载示例
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 36px 44px;
  text-align: center;
}
.glyph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background: var(--accent-soft);
  color: var(--accent);
}
h2 {
  margin: 4px 0 0;
  font-size: 17px;
  font-weight: 700;
}
.hint {
  margin: 0 0 10px;
  max-width: 360px;
}
.actions {
  display: flex;
  gap: 10px;
}
</style>
