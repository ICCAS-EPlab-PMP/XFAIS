/**
 * caps.ts — Per-module capability cards ("module skills", 2026-10-25).
 *
 * The step-by-step guides (steps/*.ts) answer "HOW do I operate this page";
 * these cards answer "WHAT can this app do for me" — the capability layer an
 * external agent needs BEFORE it routes: what each module is for, what it can
 * and cannot do, which FACTS can be queried live through run_task (with the
 * exact payload recipes), where to go when this module cannot help, and
 * zh/en routing keywords.
 *
 * Motivating failure (2026-10-25 user report): asked to process a
 * polypropylene calibrant, the agent claimed "no built-in polypropylene
 * calibrant" and wandered off — without querying list_calibrants (the built-in
 * list is live-queryable), without knowing cell-calibrant-generator can
 * GENERATE an iPP .D from unit-cell parameters, and without knowing the setup
 * form accepts a local .D file. The cards below close all three gaps, and the
 * MCP tool descriptions carry the matching golden rule: never claim the app
 * cannot do something before consulting get_modules / get_guide.
 *
 * 2026-10-26 twist that sharpens the lesson: this very machine's list HAD a
 * user-added Polypropylene_custom entry — one query disproves the claim, and
 * any doc example asserting list CONTENTS goes stale the same way. Everything
 * agent-facing below therefore states patterns and query recipes, never list
 * contents. / 2026-10-26 反转印证了教训本身：这台机器的清单里就有用户自加的
 * Polypropylene_custom——一条查询即可推翻该断言；任何断言清单内容的文档
 * 示例都会同样过时。因此下文所有面向 agent 的内容只写模式与查询配方，
 * 绝不写清单内容。
 *
 * 模块能力卡：步骤教程回答「怎么操作」，能力卡回答「能干什么」——用途/
 * 能力清单/可实时查询的事实（run_task 精确配方）/替代模块/中英路由关键词。
 * 应用内单一来源，经 guide/modules 命令序列化给外部 agent，永不与应用版本
 * 脱节。
 */

import type { Bilingual } from './types'

export interface LiveQueryRecipe {
  /** Stable description shown verbatim to the agent. */
  note: Bilingual
  /** xfais_run_task command (= backend route name). */
  command: string
  /** Exact params payload. */
  params: Record<string, unknown>
}

export interface RelatedModule {
  routeName: string
  note: Bilingual
}

export interface ModuleCaps {
  routeName: string
  /** One sentence: what this module is FOR. */
  purpose: Bilingual
  /** What it can do (bullets). */
  capabilities: Bilingual[]
  /** Facts the agent can — and SHOULD — query live instead of guessing. */
  liveQueries?: LiveQueryRecipe[]
  /** Where to go when this module cannot help. */
  related?: RelatedModule[]
  /** zh + en routing keywords (module names, synonyms, sample types…). */
  keywords: string[]
}

const zh = (s: string): Bilingual => ({ zh: s, en: '' })
const bi = (z: string, e: string): Bilingual => ({ zh: z, en: e })

export const MODULE_CAPS: Record<string, ModuleCaps> = {
  home: {
    routeName: 'home',
    purpose: bi('应用主页：模块导航与版本/更新检查。', 'App home: module navigation and version/update check.'),
    capabilities: [
      bi('列出并进入所有工作区模块。', 'Lists and enters every workspace module.'),
      bi('检查普通版/AI 版更新。', 'Checks normal/AI-build updates.'),
    ],
    keywords: ['主页', 'home', '导航', 'navigation'],
  },

  'integrate-1d': {
    routeName: 'integrate-1d',
    purpose: bi('2D 衍射图 → 1D 径向积分曲线 I(q)/I(2θ)/I(d)，批量多文件。', '2D diffraction images → 1D radial profiles I(q)/I(2θ)/I(d), batch-capable.'),
    capabilities: [
      bi('需要 .poni 几何（先标定或导入）。', 'Needs a .poni geometry (calibrate or import first).'),
      bi('多文件批量、点数/单位/范围可调、结果可导出。', 'Batch over many files; points/units/range adjustable; exportable.'),
      bi('积分结果可直接送曲线拟合工作台批量拟合。', 'Integration tables feed the curve-fitting workbench directly.'),
    ],
    related: [
      { routeName: 'calibration', note: zh('先做几何校正得到 .poni') },
      { routeName: 'poni-importer', note: zh('已有 .poni 文件时转换格式') },
      { routeName: 'curve-fitting', note: zh('对积分曲线拟合/求结晶度') },
    ],
    keywords: ['径向积分', 'radial', 'I(q)', 'iq', '2θ', 'theta', '一维', '1d', '积分曲线', 'profile'],
  },

  'integrate-azimuth': {
    routeName: 'integrate-azimuth',
    purpose: bi('2D 图 → 方位角 χ 方向积分 I(χ)（取向分布）。', '2D images → azimuthal χ profiles I(χ) (orientation distribution).'),
    capabilities: [
      bi('给定 q/2θ 窗口内沿方位角积分。', 'Integrates along χ within a q/2θ window.'),
      bi('输出弧形/取向强度分布，供取向度分析。', 'Outputs arc/orientation distributions for orientation analysis.'),
    ],
    related: [
      { routeName: 'orientation-analysis', note: zh('对 I(χ) 算 Hermans 取向度') },
      { routeName: 'integrate-cake', note: zh('需要扇形窗口积分时') },
    ],
    keywords: ['方位角', 'azimuthal', 'chi', 'χ', '取向分布', 'I(χ)'],
  },

  'integrate-cake': {
    routeName: 'integrate-cake',
    purpose: bi('CAKE 扇形窗口 2D 积分（选定 χ 扇区做 1D）。', 'CAKE sector integration: 1D within a chosen χ sector.'),
    capabilities: [bi('按方位角窗口截取扇区再径向积分。', 'Radial integration restricted to an azimuthal sector.')],
    related: [{ routeName: 'integrate-1d', note: zh('全方位角积分') }],
    keywords: ['cake', '扇形', 'sector', '窗口积分'],
  },

  'integrate-fiber': {
    routeName: 'integrate-fiber',
    purpose: bi('GIWAXS 纤维/织物 2D 积分（沿纤维轴 qᵧ–q‖ 映射）。', 'GIWAXS fiber/textile 2D integration (q⊥–q‖ mapping).'),
    capabilities: [bi('把探测器坐标换算为纤维坐标并积分。', 'Maps detector coords to fiber axes and integrates.')],
    keywords: ['giwaxs', 'fiber', '纤维', '织物', '取向薄膜', 'q平行', 'q垂直'],
  },

  viewer: {
    routeName: 'viewer',
    purpose: bi('2D 数据查看器：EDF/TIFF/H5/CBF 单帧与序列浏览。', '2D data viewer for EDF/TIFF/H5/CBF frames and sequences.'),
    capabilities: [
      bi('色标/范围调整、缩放平移、多帧序列浏览。', 'Colormap/range, zoom/pan, multi-frame browsing.'),
      bi('沿线剖面（剖面通栏布局）。', 'Line profiles along a drawn path.'),
    ],
    liveQueries: [
      {
        note: bi(
          '探测一个图像文件的真实结构（尺寸/帧数/通道/H5 数据集清单）——filePath 换成用户给的实际路径再查，不要凭扩展名猜。',
          'Probe a real image file (size/frames/channels/H5 dataset list) — substitute filePath with the user’s actual path; never guess from the extension.',
        ),
        command: 'viewer_config',
        params: { action: 'probe', filePath: '<用户图像文件的绝对路径>' },
      },
      {
        note: bi(
          '校验 .poni 几何（返回 centerX/centerY）——geometry.poniPath 换成实际路径；怀疑几何文件有问题时先查这个。',
          'Validate a .poni geometry (returns centerX/centerY) — substitute geometry.poniPath; query this when a geometry file looks suspect.',
        ),
        command: 'viewer_config',
        params: { action: 'resolve_geometry_center', geometry: { poniPath: '<.poni 文件的绝对路径>' } },
      },
    ],
    keywords: ['查看', 'viewer', '看图', '浏览', '剖面', 'profile'],
  },

  'h5-toolkit': {
    routeName: 'h5-toolkit',
    purpose: bi('H5（HDF5）探测器数据批量转换为 EDF/TIFF。', 'Batch-convert HDF5 detector data to EDF/TIFF.'),
    capabilities: [bi('批量转换、多数据集选择。', 'Batch conversion with dataset selection.')],
    liveQueries: [
      {
        note: bi(
          '扫描目录里的 H5 与参考文件（返回 datasets/totalH5/targetH5/refFile）——sourceDir 换成实际目录；先扫描再回答“有哪些数据集/多少个文件”。',
          'Scan a directory for H5 + master/ref files (returns datasets/totalH5/targetH5/refFile) — substitute sourceDir; scan BEFORE answering “which datasets / how many files”.',
        ),
        command: 'h5convert_scan',
        params: { sourceDir: '<H5 数据目录>', refSuffix: '_master', recursive: true },
      },
      {
        note: bi(
          '按扩展名列出目录内数据文件清单——suffix 换成实际扩展名（如 .h5）。',
          'List data files in a directory by extension — substitute suffix (e.g. .h5).',
        ),
        command: 'h5_list_files',
        params: { sourceDir: '<数据目录>', suffix: '.h5', recursive: true },
      },
    ],
    related: [{ routeName: 'viewer', note: zh('转换后查看') }],
    keywords: ['h5', 'hdf5', '转换', 'convert', 'edf', 'tiff'],
  },

  'mask-maker': {
    routeName: 'mask-maker',
    purpose: bi('制作/编辑掩膜文件（屏蔽死像素、光束挡块、坏区）。', 'Create/edit mask files (dead pixels, beam stop, bad regions).'),
    capabilities: [
      bi('画刷/图形/阈值方式生成掩膜，供积分与标定使用。', 'Brush/shape/threshold masking; consumed by integration and calibration.'),
    ],
    keywords: ['mask', '掩膜', '遮挡', '屏蔽', 'beamstop'],
  },

  'png-generate': {
    routeName: 'png-generate',
    purpose: bi('2D 数据批量导出 PNG 图片。', 'Batch-export 2D data as PNG images.'),
    capabilities: [bi('统一色标/范围批量出图。', 'Batch rendering with unified colormap/range.')],
    keywords: ['png', '导出图', '批量图', 'export image'],
  },

  calibration: {
    routeName: 'calibration',
    purpose: bi(
      '几何校正三模式：标样校正（Debye–Scherrer 环精修）/ 内标定标（单个已知环）/ 直通光定心（质心固定中心），产出 .poni。',
      'Geometry calibration, three modes: calibrant refine / one known ring (internal standard) / direct-beam centroid; produces .poni.',
    ),
    capabilities: [
      bi('内置 pyFAI 标样（LaB₆、CeO₂、AgBh 等）**清单可实时查询，不要凭记忆断言**。', 'Built-in pyFAI calibrants (LaB₆, CeO₂, AgBh…) — the list is LIVE-QUERYABLE; never assert from memory.'),
      bi('支持本地上传自定义 .D 标样文件（任何标样皆可，含聚合物）。', 'Accepts a LOCAL custom .D calibrant file — any material, polymers included.'),
      bi('逐一环选收峰、整环改号、框选删点、回退；最小二乘精修距离/中心/取向。', 'Ring-by-ring picking, renumber, box-erase, undo; least-squares refine of dist/centre/tilt.'),
      bi('导出 .poni 供积分模块直接使用。', 'Exports .poni for the integration views.'),
    ],
    liveQueries: [
      {
        note: bi('查询全部内置标样名（回答“有没有某标样”必须先查这个）。', 'List every built-in calibrant name (ALWAYS query this before answering “is X a built-in calibrant”).'),
        command: 'calibration',
        params: { action: 'list_calibrants' },
      },
      {
        note: bi('查询受支持的探测器型号清单。', 'List supported detector models.'),
        command: 'calibration',
        params: { action: 'list_detectors' },
      },
    ],
    related: [
      { routeName: 'cell-calibrant-generator', note: bi('经 list_calibrants 查询确认缺失的标样 → 用晶胞参数生成 .D 再上传（内置清单因机器而异，用户可加 *_custom 条目）', 'A calibrant confirmed MISSING via the list_calibrants query → GENERATE a .D from its unit cell here, then upload it (the built-in list is machine-specific; users can add *_custom entries)') },
      { routeName: 'pyfai-calib', note: zh('需要外部 pyFAI-calib2 图形工具时') },
      { routeName: 'poni-importer', note: zh('已有 .poni 直接转换') },
    ],
    keywords: ['标定', '校正', 'calibration', 'calibrant', '标样', 'poni', 'LaB6', 'LaB₆', 'CeO2', 'CeO₂', 'AgBh', '定心', '直通光', 'beam center', 'dist', '环', 'ring'],
  },

  'pyfai-calib': {
    routeName: 'pyfai-calib',
    purpose: bi('启动外部 pyFAI-calib2 图形校正工具（桌面模式）。', 'Launches the external pyFAI-calib2 GUI (desktop mode).'),
    capabilities: [bi('调用随应用捆绑的 pyFAI-calib2。', 'Runs the bundled pyFAI-calib2.')],
    related: [{ routeName: 'calibration', note: bi('应用内置标定向导（一般先用这个）', 'The built-in calibration wizard (usually prefer this)') }],
    keywords: ['pyfai', 'calib2', '外部标定'],
  },

  'cell-calibrant-generator': {
    routeName: 'cell-calibrant-generator',
    purpose: bi(
      '校正标样生成器：由晶胞参数（a,b,c,α,β,γ + 空间群/消光）计算 d 值序列并生成 .D 标样文件。',
      'Calibrant generator: computes d-spacings from unit-cell parameters (a,b,c,α,β,γ + space group) and writes a .D calibrant file.',
    ),
    capabilities: [
      bi('任意晶系/空间群，含聚合物晶体（α-iPP、PE、PA 等常见晶胞参数即可）。', 'Any crystal system / space group — polymer crystals included (α-iPP, PE, PA… just supply the cell parameters).'),
      bi('输出的 .D 在标定向导里“标样文件”来源选择本地上传即可使用。', 'The .D plugs into the calibration wizard via the LOCAL-FILE calibrant source.'),
      bi('内置常见材料示例参数。', 'Ships example parameters for common materials.'),
    ],
    liveQueries: [
      {
        note: bi(
          '页面空间群下拉用的是内置符号表；此命令核对 pyFAI 实际的空间群编号/符号/晶系（返回 spaceGroups 列表），按编号在页面检索——不要凭记忆断言编号。',
          'The page’s space-group dropdown uses a built-in symbol table; this command verifies pyFAI’s actual space-group numbers/symbols/crystal systems (returns spaceGroups) — search the page by NUMBER, never assert from memory.',
        ),
        command: 'list_space_groups',
        params: {},
      },
    ],
    related: [
      { routeName: 'calibration', note: bi('生成后去标定向导用该 .D 校正', 'After generating, run calibration with that .D') },
    ],
    keywords: ['标样生成', 'calibrant generator', '晶胞', 'unit cell', '空间群', 'space group', 'd值', '聚丙烯', 'polypropylene', 'iPP', 'PP', '聚乙烯', 'PE', 'polyethylene', '尼龙', 'PA', '聚合物标样', 'polymer calibrant'],
  },

  'bg-subtract': {
    routeName: 'bg-subtract',
    purpose: bi('样品−背景批量扣除（含透过率上限检查）。', 'Batch sample−background subtraction (transmission-cap sanity check).'),
    capabilities: [bi('逐文件配对/批量扣除、上限超限显式告知。', 'Per-file pairing, batch subtract, explicit over-limit warnings.')],
    keywords: ['背景扣除', 'background', '扣背景', 'subtract'],
  },

  transmission: {
    routeName: 'transmission',
    purpose: bi('直通束透过率测量（I₀/I 比较，多文件）。', 'Direct-beam transmission measurement (I₀/I, multi-file).'),
    capabilities: [bi('选直通束文件与样品文件批量算透过率。', 'Batch transmission from beam-empty and sample files.')],
    keywords: ['透过率', 'transmission', '直通束', 'I0'],
  },

  'image-math': {
    routeName: 'image-math',
    purpose: bi('图像间运算（加减乘除、常数运算）。', 'Image arithmetic (add/sub/mul/div, with constants).'),
    capabilities: [bi('多图四则运算与常数运算，批量输出。', 'Multi-image arithmetic and constant ops, batch output.')],
    keywords: ['图像运算', 'image math', '相减', '相加', 'multiply'],
  },

  'image-stitch': {
    routeName: 'image-stitch',
    purpose: bi('多幅图像拼接（平移对齐）。', 'Stitch multiple images (translation alignment).'),
    keywords: ['拼接', 'stitch', '拼图'],
    capabilities: [bi('行列平移拼接大图。', 'Row/column translation stitching.')],
  },

  'orientation-analysis': {
    routeName: 'orientation-analysis',
    purpose: bi('聚合物取向度分析（Hermans 取向因子等，从 I(χ) 曲线）。', 'Polymer orientation analysis (Hermans orientation factor etc. from I(χ) curves).'),
    capabilities: [
      bi('方位角积分曲线 → 取向度/半高宽/经验指数。', 'I(χ) curves → orientation, FWHM, empirical index.'),
      bi('批量多曲线。', 'Batch over many curves.'),
    ],
    related: [
      { routeName: 'integrate-azimuth', note: zh('先得到 I(χ)') },
      { routeName: 'curve-fitting', note: bi('取向分析也可在拟合工作台的聚合物面板做（逐峰）', 'Per-peak orientation is also available in the curve-fitting workbench’s polymer panel') },
    ],
    keywords: ['取向', 'orientation', 'hermans', '取向度', '方位角分布'],
  },

  'lamellar-analysis': {
    routeName: 'lamellar-analysis',
    purpose: bi('SAXS 片晶结构分析：一维相关函数（Strobl–Schneider）求长周期。', 'SAXS lamellar analysis: 1D correlation function (Strobl–Schneider) for long period.'),
    capabilities: [
      bi('I(q)→扣背景→q²I(q)→γ₁(x)→切线拟合长周期。', 'I(q)→background→q²I(q)→γ₁(x)→tangent fit for Lp.'),
      bi('单边 q 上下限、多文件批量。', 'One-sided q limits, batch files.'),
    ],
    keywords: ['片晶', 'lamellar', '长周期', 'long period', 'saxs', '相关函数', 'correlation'],
  },

  'curve-fitting': {
    routeName: 'curve-fitting',
    purpose: bi(
      '衍射曲线拟合工作台（纯前端）：五步流程 数据→基线→放峰→拟合→报告 + 聚合物分析（结晶度/取向/Kβ）。',
      'Diffraction curve-fitting workbench (fully in-browser): data→baseline→peaks→fit→report + polymer analyses (crystallinity/orientation/Kβ).',
    ),
    capabilities: [
      bi('多种峰形（Gaussian/Lorentz/Pearson/Voigt…）可拖锚实时调参。', 'Multiple peak shapes with live draggable anchors.'),
      bi('多曲线批量拟合；X-FAIS 积分结果可直接导入（多列按强度列拆分）。', 'Batch fitting; X-FAIS integration tables import directly.'),
      bi('聚合物分析：结晶度（峰分类）、取向（I(χ) 逐峰）、iPP Kβ（Turner-Jones）。', 'Polymer panel: crystallinity, per-peak orientation, iPP Kβ (Turner-Jones).'),
      bi('参数/曲线/TXT 导出。', 'Parameter/curve/TXT export.'),
    ],
    related: [
      { routeName: 'integrate-1d', note: zh('先积分得到曲线') },
      { routeName: 'orientation-analysis', note: zh('批量取向分析的另一入口') },
    ],
    keywords: ['拟合', 'fitting', '峰', 'peak', '结晶度', 'crystallinity', 'Kβ', 'kbeta', 'turner', 'jones', 'voigt', '基线', 'baseline', '批量拟合', 'batch'],
  },

  'poni-importer': {
    routeName: 'poni-importer',
    purpose: bi('已有 .poni 几何文件转换/接入（供积分模块使用）。', 'Convert/plug in an existing .poni geometry for the integration views.'),
    keywords: ['poni', '几何导入', 'geometry import'],
    capabilities: [bi('.poni 解析与换算。', '.poni parsing and conversion.')],
    related: [{ routeName: 'calibration', note: zh('没有 .poni 时先标定') }],
  },

  settings: {
    routeName: 'settings',
    purpose: bi('应用设置：界面语言、积分默认算法、批处理并行（实验性）、OpenMP 线程、AI 选项。', 'App settings: UI language, default integration algorithm, batch parallelism (experimental), OpenMP threads, AI options.'),
    keywords: ['设置', 'settings', '语言', 'language', '并行', 'OpenMP'],
    capabilities: [
      bi('语言即时生效；默认算法只影响新任务。', 'Language applies instantly; the default algorithm only affects new tasks.'),
      bi('OpenMP 线程数修改后需重启应用生效。', 'OpenMP thread count needs an app restart to take effect.'),
    ],
  },
}

/** Card for one route (null when unknown). */
export function capsOf(routeName: string): ModuleCaps | null {
  return MODULE_CAPS[routeName] ?? null
}
