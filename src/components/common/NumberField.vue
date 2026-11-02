<template>
  <!--
    Attributes (class / step / min / max / placeholder / data-testid / …)
    fall through to this input.
    class / step / min / max / placeholder / data-testid 等属性透传到本输入框。
  -->
  <input
    type="number"
    :value="draft"
    @focus="focused = true"
    @blur="focused = false"
    @input="onInput"
    @change="onChange"
  />
</template>

<script setup lang="ts">
/**
 * NumberField.vue — 编辑结束才提交的数字输入框
 * NumberField.vue — number input that commits when editing ends
 *
 * A plain `:value` + parse-on-`@input` pair round-trips through the parent
 * model on every keystroke: typing "1.0" parses to 1 and the prop write-back
 * rewrites the focused input to "1" (Vue's focused-input guard only covers
 * `v-model`, not manual `:value` bindings), discarding what the user just
 * typed. This component instead commits only when editing ends:
 *
 * - while typing, the raw text stays in a local draft and NOTHING is emitted
 *   (no model writes, no live rewrites, no mid-edit fights);
 * - on blur / Enter (`change`), the complete value is emitted once — user
 *   edits take effect automatically, with no confirm button;
 * - external changes (seed_from_poni / auto-detect / unit toggle) still land
 *   in the field, except while an uncommitted edit is in progress;
 * - if the parent transforms or refuses a commit (clamp, default, ignored),
 *   the field resyncs to the effective value once editing has ended.
 *
 * 手写 `:value` + `@input` 解析回传会在每次按键后把父模型归一化的数值写
 * 回输入框（输入 "1.0" 被解析成 1 后随即改写成 "1"）。本组件改为"编辑结束
 * 才提交"：
 *
 * - 输入过程中原始文本只留在本地草稿里，什么都不发出（不写模型、不改写、
 *   不打断输入）；
 * - 失焦或回车（`change`）时一次性发出完整值——修改自动生效，无需确认；
 * - 外部变化（PONI 初始化 / 自动探测 / 单位切换）照常回填，但进行中的未
 *   提交编辑优先；
 * - 若父组件改写或拒绝了提交值（钳制 / 默认值 / 忽略），编辑结束后输入框
 *   回显实际生效值。
 */
import { ref, watch } from 'vue'

const props = defineProps<{
  /** Current value; null renders as an empty field. / 当前值；null 显示为空。 */
  modelValue: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const draft = ref(props.modelValue == null ? '' : String(props.modelValue))
const focused = ref(false)

// Uncommitted keystrokes exist → an in-progress edit outranks external
// prop changes until it is committed.
// 存在未提交的按键输入 → 进行中的编辑优先于外部属性变化，直至提交。
let dirty = false

// The value this component last committed, awaiting the parent's echo.
// undefined = nothing in flight, so any prop change counts as external.
// 本组件最近提交、等待父模型回显的值。undefined = 无在途提交，此时属性变
// 化一律视为外部修改。
let emitted: number | null | undefined

function parseDraft(): number | null {
  const num = parseFloat(draft.value)
  return Number.isFinite(num) ? num : null
}

// Keep the draft aligned with the DOM text on every keystroke: without this,
// any sibling-driven re-render would patch the focused input back to the
// stale draft value (the original "1.0 becomes 1" clobber, re-entered via a
// different path). Still emits nothing — committing happens on change.
// 每次按键都让草稿跟随输入框文本：否则兄弟组件引发的重渲染会把聚焦中的
// 输入框改回过期草稿（"1.0 变 1" 的另一条复发路径）。但此处不发出任何值
// ——提交发生在 change。
function onInput(event: Event): void {
  draft.value = (event.target as HTMLInputElement).value
  dirty = true
}

// change fires on blur / Enter (and per spinner click), i.e. exactly when the
// edit is finished: emit the complete value once. The empty / unparseable
// draft commits as null; parents decide whether that clears, defaults, or is
// ignored (and the watch below then shows the effective value).
// change 在失焦 / 回车（以及每次点微调按钮）时触发，即编辑结束的那一刻：
// 一次性发出完整值。空或不可解析的草稿按 null 提交；由父组件决定是清空、
// 取默认还是忽略（随后 watch 会回显实际生效值）。
function onChange(event: Event): void {
  draft.value = (event.target as HTMLInputElement).value
  emitted = parseDraft()
  dirty = false
  emit('update:modelValue', emitted)
}

watch(
  () => props.modelValue,
  (value) => {
    if (value === emitted) {
      // Our own echo — keep the user's text ("1.0", trailing zeros …).
      // 自己的回显——保留用户的原始文本（"1.0"、末尾的 0 等）。
      emitted = undefined
      return
    }
    emitted = undefined
    if (focused.value && dirty) {
      // An uncommitted edit is in progress — never fight the user.
      // 进行中的编辑尚未提交——绝不打断用户。
      return
    }
    draft.value = value == null ? '' : String(value)
  },
)
</script>
