<script setup lang="ts">
/**
 * 教程提示图标（2026-10-23 用户要求：教程类内容以 ？ 图标展示，鼠标移上去
 * 显示文字，图标要显眼）。明显的蓝色圆形 ？ 徽标，hover / 键盘聚焦弹出说明
 * 气泡；纯 CSS（hover + focus-within），无依赖。
 */
defineProps<{
  /** Tooltip text (shown on hover / keyboard focus). / 悬停显示的说明文字。 */
  text: string
  /** Icon diameter in px (default 16). / 图标直径（默认 16px）。 */
  size?: number
}>()
</script>

<template>
  <span
    class="help"
    :style="size ? { '--hs': `${size}px` } : undefined"
    tabindex="0"
  >
    <span class="help-dot" aria-hidden="true">?</span>
    <span class="help-pop" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.help {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  cursor: help;
  --hs: 16px;
}

.help-dot {
  width: var(--hs);
  height: var(--hs);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
  font-size: calc(var(--hs) * 0.62);
  font-weight: 700;
  line-height: 1;
  user-select: none;
  box-shadow: 0 0 0 2.5px color-mix(in srgb, var(--accent) 22%, transparent);
}

.help-pop {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 7px);
  transform: translateX(-50%) translateY(3px);
  width: max-content;
  max-width: 280px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-1);
  color: var(--text-1);
  font-size: var(--fs-small);
  font-weight: 400;
  line-height: 1.55;
  text-align: left;
  white-space: normal;
  box-shadow: 0 4px 14px rgb(15 23 42 / 14%);
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.12s ease,
    transform 0.12s ease;
  z-index: 60;
}

.help:hover .help-pop,
.help:focus-visible .help-pop {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.help:focus {
  outline: none;
}

.help:focus-visible .help-dot {
  box-shadow:
    0 0 0 2.5px color-mix(in srgb, var(--accent) 22%, transparent),
    0 0 0 2px var(--bg-1),
    0 0 0 3.5px var(--accent);
}
</style>
