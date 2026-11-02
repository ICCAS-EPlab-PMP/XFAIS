/**
 * manuals.ts — Assembler for the per-module DETAILED manuals (2026-10-27).
 *
 * Authoring lives in three files to keep each grounded and reviewable:
 *   - this file: calibration + curve-fitting (the format exemplars);
 *   - manuals-a.ts: integration / image family (authored against its views);
 *   - manuals-b.ts: analysis / utility family (authored against its views).
 * Every manual MUST be grounded in the actual view code — the workflow is the
 * REAL UI order, not an idealized one. manuals.ts 把各文件汇总为
 * MODULE_MANUALS，经 caps.ts 能力卡随 guide/modules 命令下发。
 */

import type { ModuleManual } from './types'
import { MANUALS_A } from './manuals-a'
import { MANUALS_B } from './manuals-b'

const zh = (s: string): { zh: string; en: string } => ({ zh: s, en: '' })

// ── calibration —— 格式范例（三模式，含教学优先提示） ─────────────────────────

const CALIBRATION_MANUAL: ModuleManual = {
  overview: zh(
    '几何校正：把一张衍射图变成精确的探测器几何（.poni）。三种模式——标样校正' +
      '（标准标样的 Debye–Scherrer 环，逐环拾取后最小二乘精修）、内标定标（单个已知 d 间距的环，' +
      '适合样品自带内标）、直通光定心（直通光斑强度质心定中心，再换标样图只精修距离）。' +
      '产出的 .poni 供 1D 积分、方位角积分、CAKE、掩膜等模块直接使用。',
  ),
  inputs: [
    zh('一张 2D 衍射图（EDF/TIFF/H5/CBF）：标样校正用标准标样图；内标定标用带内标环的样品图。'),
    zh('直通光定心需要两张图：第一张直通光图（求质心定中心），第二张标样图（精修距离）。'),
    zh('标样校正需指定标样材质：内置清单可实时查询（run_task: calibration, action=list_calibrants），也支持本地上传自定义 .D 文件。'),
    zh('探测器型号可实时查询（run_task: calibration, action=list_detectors）。'),
    zh('估算的探测器距离有助于收敛：预设 WAXS≈130mm / SAXS≈2500mm 可直接选用；未知时先用「点选初猜中心」。'),
  ],
  workflow: [
    {
      title: zh('选择模式'),
      detail: zh('设置区三选一：标样校正 / 内标定标 / 直通光定心；切换后步骤栏随之变化。'),
    },
    {
      title: zh('加载图像'),
      detail: zh('标样校正：加载标样图并确认探测器与标样材质；直通光定心：先加载直通光图。'),
    },
    {
      title: zh('确定中心初猜'),
      detail: zh('直通光：框选光斑后自动算强度加权质心；标样支路：点「点选初猜中心」在图上点环心（会自动重排环号）。'),
    },
    {
      title: zh('逐环拾取引导点'),
      detail: zh('沿当前环在画布上点 ≥3 个引导点，点「完成本环」收环；数字框可改环号；环带 ±dr 默认 5px 可调。'),
    },
    {
      title: zh('精修几何'),
      detail: zh('勾选放开/固定各参数后点「精修」，看 χ² 收敛；直通光支路中心固定、只优化距离。'),
    },
    {
      title: zh('核对与导出'),
      detail: zh('几何预览里核对理论环与实测环叠加；确认后导出 .poni，积分模块即可直接使用。'),
    },
  ],
  outputs: [
    zh('.poni 几何文件：距离、中心、三个取向角、波长，后续模块免重配。'),
    zh('精修后的 χ² 与各参数值，可用于报告或存档。'),
  ],
  pitfalls: [
    zh('环号标错会让精修收敛到错误几何；用户亲手指定的环号（汇总表带 ★）在自动重排时会被保留。'),
    zh('从未设中心时默认以图像中心作初猜：初猜偏离过远时精修可能陷入局部极小——先点选中心或用首环圆拟合种子。'),
    zh('直通光支路换图、换支路、改质心都会使已建的标样会话失效，需要重新加载标样图（中心保留）。'),
    zh('内标定标只需一个已知 d 间距的环（≥3 点），不要按标样校正的流程要求多环。'),
    zh('精修是迭代过程：初猜差时先放开较少参数（距离+中心），收敛后再放开取向角。'),
  ],
  agentTips: [
    zh('文件选择对话框必须由用户完成：highlight 加载按钮并说明需要哪张图，不要假装已选文件。'),
    zh('画布拾取引导点可代做：先 screenshot 读环的位置，再用 canvasX/canvasY 点击（CSS 像素），每环 ≥3 点后点「完成本环」。'),
    zh('回答「有没有某标样」之前必须先 run_task 查询 list_calibrants；确认缺失时引导用户到「校正标样生成器」按晶胞参数生成 .D 或本地上传。'),
    zh('精修与导出是关键动作：先 confirm 用户同意，或 highlight 对应按钮引导用户自己点。'),
  ],
}

// ── curve-fitting —— 格式范例（五步工作台 + 聚合物分析） ──────────────────────

const CURVE_FITTING_MANUAL: ModuleManual = {
  overview: zh(
    '衍射曲线拟合工作台（纯前端，浏览器内计算、无需后端）：数据→基线→放峰→拟合→报告五步流程，' +
      '支持多峰多种峰形、可拖锚实时调参、多曲线批量拟合；报告页另有可选的聚合物分析' +
      '（结晶度/取向/iPP Kβ，默认关闭、逐项开启）。X-FAIS 积分结果可直接导入。',
  ),
  inputs: [
    zh('一维曲线：.PRN/.CSV/.TSV/.xy 文本、多列积分表（按强度列拆成多条曲线）、多段 .xy（每段一条）。'),
    zh('也可粘贴文本到数据录入框解析；或从积分模块导出后直接导入。'),
    zh('无后端依赖：web/桌面模式行为一致；拟合在浏览器 Web Worker 中运行。'),
  ],
  workflow: [
    {
      title: zh('数据'),
      detail: zh('导入/粘贴曲线；需要时平滑（SG/滑动平均/FFT 低通）；左右滑可排除坏区段（仅影响拟合参与，导出仍用真值）。'),
    },
    {
      title: zh('基线'),
      detail: zh('自动基线四步流水线（端点/渐进/二阶导 × 三种选优）或手选基线点；可设「联合基线」随拟合一起精修。'),
    },
    {
      title: zh('放峰'),
      detail: zh('图上点击放峰（默认伪 Voigt，X 射线五种峰形可选）；主锚拖中心/峰高，半高双柄拖宽度；或残差法/二阶导自动寻峰。'),
    },
    {
      title: zh('拟合'),
      detail: zh('点「拟合」看迭代遥测与 χ² 收敛；改参数 300ms 防抖自动重拟合；停止=保留最优，中止=回滚快照。'),
    },
    {
      title: zh('报告'),
      detail: zh('统计量 + 逐峰卡（参数±标准误/FWHM/面积/占比）+ 残差图；可导出参数 CSV、拟合曲线 CSV、TXT 报告。'),
    },
    {
      title: zh('聚合物分析（可选）'),
      detail: zh('结晶度（逐峰分类 结晶/非晶）、取向（I(χ) 逐峰 Hermans）、iPP Kβ（逐峰指派 Turner-Jones）；默认全关，开哪个算哪个。'),
    },
  ],
  outputs: [
    zh('拟合参数 CSV / 密采样拟合曲线 CSV / TXT 报告（R²、χ²、逐峰表）。'),
    zh('聚合物分析三表（结晶度、取向度、Kβ 面积比），数值来自拟合面积。'),
  ],
  pitfalls: [
    zh('半高柄拖过中心曾把宽度冻在极小值——参数守卫会自动修正并 toast 提示，修正后可继续拟合。'),
    zh('排除的区段在后续步骤图上断开且无 × 标记，回数据步才显示 ×；「恢复全部数据」可撤销。'),
    zh('自动重拟合运行中再点「拟合」会被拒绝（toast「已有拟合正在运行」），先停止或等收敛。'),
    zh('聚合物分析默认关闭且不计算：未开启的项目不占时间，开启后数值才出现。'),
    zh('批量拟合在多选导入后进行：底部曲线条切换当前曲线，逐条调好再批量执行。'),
  ],
  agentTips: [
    zh('曲线文件导入必须由用户完成；也可以让用户把数据粘贴进录入框，再由 agent 代点后续步骤。'),
    zh('放峰可代做：screenshot 读峰位后用 canvasX/canvasY 点击放峰；点手柄是拖拽语义，点空白才是放峰。'),
    zh('拟合与导出建议先 confirm；报告数值（R²/χ²/逐峰参数）读报告页，不要凭拟合遥测猜测。'),
    zh('被问「结晶度/取向/Kβ」时：先确认聚合物分析是否开启，未开启就 highlight 报告页开关并解释三项含义。'),
  ],
}

/** Full manual registry — module key = routeName（与 MODULE_CAPS 一致）. */
export const MODULE_MANUALS: Record<string, ModuleManual> = {
  calibration: CALIBRATION_MANUAL,
  'curve-fitting': CURVE_FITTING_MANUAL,
  ...MANUALS_A,
  ...MANUALS_B,
}
