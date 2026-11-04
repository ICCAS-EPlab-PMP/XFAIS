// maskDisplay — shared mask-overlay display style (red / white / violet).
// 掩膜显示风格——标定画布与掩膜工具共用的三档叠加配色。
//
// Why a module-level Vue ref: the same preference drives TWO independent
// surfaces (CalibrationView's render bar and MaskMaker's display panel) and
// TWO canvases. A module-level ref keeps them in sync reactively — no event
// bus, no prop drilling across views — while localStorage persists the choice
// across restarts. Bad/stale stored values fall back to 'red' so a corrupted
// entry can never break the canvas renderers.
// 为什么用模块级 ref：同一偏好要驱动两处设置界面（标定渲染条、掩膜工具显示
// 面板）与两个画布。模块级 ref 让它们响应式同步——无需事件总线、无需跨视图
// 传 props；localStorage 负责重启后保留选择。坏值回退 'red'，损坏的存储项
// 不会让画布渲染崩溃。
//
// Tier semantics / 三档语义:
//   red    — translucent red (default): marks masked areas, keeps detail visible
//            半透明淡红（默认）：标记掩膜区域，其下细节仍可见
//   white  — solid opaque white: fully hides the data beneath (effective area)
//            不透明纯白：完全遮挡下方数据，直观呈现有效探测范围
//   violet — 5%-opacity deep violet: nearly non-intrusive extent hint
//            5% 透明度深紫：几乎不干扰原图判读，仅提示掩膜大致范围
import { ref } from 'vue'

export type MaskDisplayStyle = 'red' | 'white' | 'violet'

/** Option order also drives the <select> rendering in both views. */
/** 选项顺序同时决定两个视图下拉框的渲染顺序。 */
export const MASK_DISPLAY_STYLES: MaskDisplayStyle[] = ['red', 'white', 'violet']

const STORAGE_KEY = 'xfaos.display.maskStyle'
const DEFAULT_STYLE: MaskDisplayStyle = 'red'

function readStored(): MaskDisplayStyle {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw && (MASK_DISPLAY_STYLES as string[]).includes(raw)) {
      return raw as MaskDisplayStyle
    }
  } catch {
    /* storage unavailable (privacy mode / file://) — memory-only below.
       存储不可用（隐私模式 / file://）——退化为仅内存态。 */
  }
  return DEFAULT_STYLE
}

const maskStyleRef = ref<MaskDisplayStyle>(readStored())

/** Current display style. Reactive: reads the module ref, so callers inside
 *  templates/computed track changes made from ANY view. */
/** 当前显示风格。响应式：读模块级 ref，模板/computed 中的调用会跟随任意
 *  视图发起的更改。 */
export function getMaskDisplayStyle(): MaskDisplayStyle {
  return maskStyleRef.value
}

/** Set the style and persist it; every consumer of the shared ref updates at
 *  once. / 写入风格并持久化；所有共享 ref 的消费者立即更新。 */
export function setMaskDisplayStyle(s: MaskDisplayStyle): void {
  maskStyleRef.value = s
  try {
    localStorage.setItem(STORAGE_KEY, s)
  } catch {
    /* storage full/blocked — keep in-memory state / 存储异常时仅保留内存态 */
  }
}
