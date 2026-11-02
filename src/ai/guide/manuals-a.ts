/**
 * manuals-a.ts — Detailed module manuals, integration / image family.
 * Modules: integrate-1d, integrate-azimuth, integrate-cake, integrate-fiber,
 * viewer, h5-toolkit, png-generate, mask-maker.
 *
 * Authored against the actual views (grounded workflow, real UI order).
 * zh is complete; en may be empty — serialization falls back to zh.
 */

import type { ModuleManual } from './types'

const zh = (s: string): { zh: string; en: string } => ({ zh: s, en: '' })
const bi = (z: string, e: string): { zh: string; en: string } => ({ zh: z, en: e })

// ── integrate-1d ─────────────────────────────────────────────────────────────

const INTEGRATE_1D_MANUAL: ModuleManual = {
  overview: bi(
    '批量一维径向积分：一次导入多张 2D 衍射图，按 PONI（或手动）几何做径向平均，' +
      '得到 I(q)/I(2θ) 曲线；可设掩膜、偏振、输出单位、点数与积分算法，结果可导出文本或直接进曲线拟合。',
    'Batch 1-D radial integration of 2D diffraction images with PONI or manual geometry; produces I(q)/I(2theta) profiles.',
  ),
  inputs: [
    zh('2D 衍射图（.edf/.tif/.tiff/.h5/.hdf5）：可多选、导入文件夹（桌面）或拖放到文件区；导入模式选替换或追加。'),
    zh('几何参数：优先 .poni（几何区切「PONI 文件」并选择）；没有就用手动模式填像素尺寸、距离、波长、束心——默认值是占位值，必须核实。'),
    zh('标定向导的「去积分」会带 PONI 参数跳转并自动绑定几何，页面提示「已导入校正参数」。'),
    zh('可选：自定义掩膜文件（「掩膜导入」折叠区，默认收起）与偏振因子。'),
    zh('输出单位/径向点数/算法在侧栏「输出单位」与「高级选项」；4D H5 还需在预览下方选数据集、通道与帧。'),
  ],
  workflow: [
    {
      title: zh('加载图像'),
      detail: zh('主区「数据文件」点「选择文件」或「导入文件夹」；确认替换/追加与文件计数，批量时每文件各出一条曲线。'),
    },
    {
      title: zh('设置几何'),
      detail: zh('侧栏顶部几何区选 PONI 或手动参数；预览图十字与「光束中心」读数随几何刷新，据此核对束心。'),
    },
    {
      title: zh('掩膜与偏振'),
      detail: zh('展开「掩膜导入」设有效值范围、死像素阈值或自定义掩膜；需要时在偏振卡填偏振因子。'),
    },
    {
      title: zh('单位与点数'),
      detail: zh('「输出单位」选 q(nm⁻¹)/q(Å⁻¹)/2θ(deg)/2θ(rad)；展开「高级选项」设点数、算法、积分引擎、立体角与空 bin。'),
    },
    {
      title: zh('H5 数据集'),
      detail: zh('导入 .h5 后预览区出现数据集/通道/帧选择器；切换会重渲染预览，运行积分用的就是这里的选择。'),
    },
    {
      title: zh('运行积分'),
      detail: zh('点「运行积分」，进度条按文件推进；中途取消只停止接收结果，后端任务不会真正中止。'),
    },
    {
      title: zh('核对曲线'),
      detail: zh('结果区折线图按文件显示多条曲线，x 轴随输出单位，可切 y 轴对数；错误提示在下方。'),
    },
    {
      title: zh('导出结果'),
      detail: zh('结果下方导出对话框选 txt/csv/hdf5 与模式：单文件把多条曲线并表，分别导出则每曲线一文件。'),
    },
  ],
  outputs: [
    zh('I(q)/I(2θ) 曲线（每文件一条），可导出 txt/csv/hdf5；各文件 x 网格一致时用单文件，否则分别导出。'),
    zh('导出的多列积分表可直接导入衍射曲线拟合工作台（按强度列拆成多条曲线）。'),
    zh('页面结果不落盘：不导出就离开页面会丢失，需要留档请先导出。'),
  ],
  pitfalls: [
    zh('部分文件失败时页面只画成功曲线、不弹失败提示（后端返回的失败清单被忽略）——曲线数少于文件数即有文件被跳过。'),
    zh('「取消」只断开前端监听，后端积分仍在跑；结果会被丢弃但计算不中断。'),
    zh('高级选项里的径向上下限在本页不生效（后端只取点数/单位/算法等），要限区间请用掩膜或导出后裁剪。'),
    zh('批量 H5 时数据集/通道/帧选择对所有文件统一生效；结构不同的 H5 会失败或被跳过。'),
    zh('切换输出单位会把径向上下限清空，避免旧单位数值残留；切完要重新确认范围。'),
  ],
  agentTips: [
    zh('图像与 .poni 的选择必须由用户完成：highlight「选择文件」并说明要哪种图/几何，不要假装已选。'),
    zh('本页画布是图像加不可点击的叠加层，canvasX/canvasY 的合成点击落不到图像点击处理上，不要用它改参数或读像素；只做按钮级操作。'),
    zh('运行与导出先 confirm（长任务、写文件）；缺事实先查 run_task 的 viewer_config：action=probe 读尺寸/帧/通道，action=resolve_geometry_center 校验 .poni 的束心。'),
    zh('web 模式没有保存/目录对话框，导出与文件夹导入不可用；需要导出时引导用户用桌面版。'),
  ],
}

// ── integrate-azimuth ────────────────────────────────────────────────────────

const INTEGRATE_AZIMUTH_MANUAL: ModuleManual = {
  overview: bi(
    '方位角 χ 积分：在指定径向窗口内沿 χ 求强度分布 I(χ)，用于取向/织构与弧形分析。' +
      '可设径向单位与窗口、χ 范围与单位、χ/径向点数与积分算法；预览图用灰色圆环标出真正参与积分的像素带。',
    'Azimuthal chi integration within a radial window; produces I(chi) profiles for orientation and texture analysis.',
  ),
  inputs: [
    zh('2D 衍射图（.edf/.tif/.tiff/.h5/.hdf5），可多选、导入文件夹或拖放；每文件各出一条 I(χ)。'),
    zh('几何：.poni 文件或手动参数（像素尺寸、距离、波长、束心）。'),
    zh('径向窗口与径向单位（默认 q(Å⁻¹) 0.98–1.02；换单位会切到该单位的预设窗口）。'),
    zh('方位角范围（默认 -180–180 全周）与 χ 输出单位（度/弧度）。'),
    zh('可选：自定义掩膜；4D H5 需在预览区选数据集/通道/帧；χ 点数默认 360、径向点数默认 100。'),
  ],
  workflow: [
    {
      title: zh('加载图像'),
      detail: zh('主区选文件/导入文件夹/拖放，确认替换或追加；多文件会各自积分成一条曲线。'),
    },
    {
      title: zh('设置几何'),
      detail: zh('侧栏几何区选 PONI 或手动；预览十字与束心读数随几何更新，先确认中心正确再看窗口。'),
    },
    {
      title: zh('径向窗口'),
      detail: zh('「径向范围」选单位并填上下限（须下限<上限）；预览图灰色圆环显示真正参与积分的像素带。'),
    },
    {
      title: zh('方位角范围'),
      detail: zh('填起始/终止（0°=正右、屏幕顺时针增加，须起始<终止）；非全周时圆环只显示该扇区。'),
    },
    {
      title: zh('χ 单位与点数'),
      detail: zh('选 χ(度)/χ(弧度)；设 npt（χ 点数）与 npt_rad（径向点数），选积分算法与是否剔除空 bin。'),
    },
    {
      title: zh('运行积分'),
      detail: zh('点「开始积分」；多文件时进度条按文件推进，失败文件以警告 toast 列出。'),
    },
    {
      title: zh('导出结果'),
      detail: zh('结果图下方导出对话框选 txt/csv/hdf5 与单文件/分别导出；单文件要求各文件 χ 网格一致。'),
    },
  ],
  outputs: [
    zh('I(χ) 曲线（每文件一条），导出 txt/csv/hdf5，供取向分析（Hermans）或报告使用。'),
    zh('灰色圆环只是窗口确认叠加，不进结果；换窗口要重新运行积分。'),
  ],
  pitfalls: [
    zh('本页的偏振因子没有下传、也不做立体角校正（后端只接收数据/范围/掩膜/算法），调了不会改变结果。'),
    zh('起始方位角必须小于终止：要跨 0° 的对称区间就填全周或等价负角区间，不要靠反转数值。'),
    zh('换径向单位会把窗口重置为该单位预设值（不是数值换算）；自定义窗口要重填。'),
    zh('灰色圆环只是显示辅助：实际参与积分的是窗口与掩膜的交集，改掩膜不会改变圆环形状。'),
    zh('多文件共用同一窗口与数据集选择；几何不同的文件径向窗口含义不同，应分批处理。'),
  ],
  agentTips: [
    zh('图像与 .poni 由用户选择；highlight 按钮并说明要哪张图，不要代选。'),
    zh('本页画布只显示预览与叠加层，canvasX/canvasY 点击不会触发任何拾取；窗口与点数让用户在侧栏填，agent 只做解释与按钮级操作。'),
    zh('运行/导出先 confirm；回答窗口是否合理前，先用 run_task 的 viewer_config（action=resolve_geometry_center 查 .poni 束心，action=probe 读图像尺寸），不要凭文件名猜。'),
    zh('要说明本页没有立体角/偏振控制（不是隐藏选项），需要这些校正先确认支持的模块。'),
  ],
}

// ── integrate-cake ───────────────────────────────────────────────────────────

const INTEGRATE_CAKE_MANUAL: ModuleManual = {
  overview: bi(
    'CAKE 方位角窗口积分：把 1D 径向积分限制在指定 χ 扇区内，用于织构、应变与各向异性样品。' +
      '预览图用灰色蒙版盖住未选区域并画两条边界线，可选顺时针/逆时针扫掠约定与输出单位。',
    'CAKE sector integration: a 1-D radial profile restricted to a chi sector, with a gray mask over unselected regions.',
  ),
  inputs: [
    zh('2D 衍射图（.edf/.tif/.tiff/.h5/.hdf5），可多选、导入文件夹或拖放。'),
    zh('几何：.poni 文件或手动参数。'),
    zh('方位角扇区（起始/终止，默认 -180–180 全周）与扫掠方向（顺/逆时针）。'),
    zh('径向范围与输出单位：在「输出单位」与「高级选项」里设置，留空表示全范围。'),
    zh('可选掩膜、偏振因子与积分算法；4D H5 需选数据集/通道/帧。'),
  ],
  workflow: [
    {
      title: zh('加载图像'),
      detail: zh('主区选文件/导入文件夹/拖放并确认替换或追加；每文件各出一条扇区曲线。'),
    },
    {
      title: zh('设置几何'),
      detail: zh('侧栏几何区选 PONI 或手动；预览十字与束心读数随几何刷新。'),
    },
    {
      title: zh('划定扇区'),
      detail: zh('「方位角范围」填起始/终止（0°=正右、屏幕顺时针增加）；勾「灰色蒙版显示未选区域」看预览，边界线即积分边界。'),
    },
    {
      title: zh('选扫掠方向'),
      detail: zh('勾「顺时针」或切「逆时针」：逆时针会把角度取负再送 pyFAI，预览与实际积分同步变化。'),
    },
    {
      title: zh('单位与径向范围'),
      detail: zh('「输出单位」选 q/2θ；展开「高级选项」填径向上下限（留空=全范围）、径向点数、算法、立体角与空 bin。'),
    },
    {
      title: zh('运行积分'),
      detail: zh('点「运行 CAKE 积分」，进度条推进；失败文件以警告 toast 列出，结果图标题带扇区范围。'),
    },
    {
      title: zh('导出结果'),
      detail: zh('导出对话框选 txt/csv/xy/hdf5：xy 为两列纯文本，hdf5 保留多曲线；单文件/分别导出可选。'),
    },
  ],
  outputs: [
    zh('扇区内的 I(q)/I(2θ) 曲线（每文件一条），导出 txt/csv/xy/hdf5。'),
    zh('同一数据不同扇区的结果可对比织构/取向差异（分批运行、各自导出）。'),
  ],
  pitfalls: [
    zh('扇区必须起始<终止；不能用一个跨 360° 的区间，需要对面两个扇区就分两次运行。'),
    zh('切换输出单位会清空径向上下限（不是换算），要重新填，否则可能按全范围积分。'),
    zh('顺/逆时针只改送进后端的角度符号，曲线本身不记录该约定——报告时需自己标注方向。'),
    zh('默认方位角是全周 -180–180，不手动收窄时结果与普通 1D 积分接近，容易被误当成取向结果。'),
    zh('多文件共用同一扇区与几何；不同几何的文件其扇区对应像素不同，需分批。'),
  ],
  agentTips: [
    zh('图像与 .poni 由用户选择；highlight 并说明用途，不要代选。'),
    zh('画布无拾取交互：canvasX/canvasY 点击不会改扇区；扇区靠侧栏数值框，让用户填或 highlight 解释。'),
    zh('运行/导出先 confirm；先用 run_task 的 viewer_config（action=resolve_geometry_center）校验几何再看预览，不要凭灰色区域猜角度。'),
    zh('解释「顺时针/逆时针」时说明它只影响角度符号、不改图像；必要时给出等价负角区间。'),
  ],
}

// ── integrate-fiber ──────────────────────────────────────────────────────────

const INTEGRATE_FIBER_MANUAL: ModuleManual = {
  overview: bi(
    'GIWAXS 掠入射 2D 积分：把探测器图按纤维/薄膜几何映射到 qip×qoop 平面；一次积分全部导入文件并缓存，主图显示第一张。' +
      '附带 ROI 区域 1D 剖面（面内/面外）与出版风格 PNG 导出（matplotlib 预览、批量出图）。',
    'GIWAXS grazing-incidence 2-D integration onto qip x qoop with a batch cache, ROI 1-D profiles and PNG export.',
  ),
  inputs: [
    zh('2D 衍射图（.edf/.tif/.tiff/.h5/.hdf5）：只导入要整批处理的文件——「预览积分」会对全部文件执行。'),
    zh('几何：.poni 或手动（像素、距离、波长、束心，另可给 rot1/rot2/rot3）；PONI 模式下需勾「覆盖 PONI 旋转」才用这三个角。'),
    zh('样品角度：样品方向 1–8、入射角、倾斜角（掠入射几何）。'),
    zh('坐标单位（面内/面外各选）与范围；网格点数 npt_ip/npt_oop（默认各 400，必须 ≥50）。'),
    zh('可选掩膜、偏振因子、立体角校正；PNG 导出必须已有一次积分生成的结果缓存。'),
  ],
  workflow: [
    {
      title: zh('加载图像'),
      detail: zh('主区选文件/导入文件夹/拖放；一次导入的全部文件都会参与积分，先删掉不需要的。'),
    },
    {
      title: zh('几何与旋转'),
      detail: zh('展开「几何与校正」选 PONI 或手填；PONI 模式勾「覆盖 PONI 旋转」后 rot1/rot2/rot3 才覆盖文件值。'),
    },
    {
      title: zh('样品角度'),
      detail: zh('设样品方向 1–8（翻转/旋转约定）、入射角与倾斜角；它们直接决定 qip/qoop 映射。'),
    },
    {
      title: zh('坐标与范围'),
      detail: zh('选面内/面外单位；默认「自动范围」由 pyFAI 推算，关掉后填 ip/oop 上下限。'),
    },
    {
      title: zh('网格与算法'),
      detail: zh('设 npt_ip/npt_oop（均须 ≥50）；算法默认 pyFAI 不分裂，显式 splitpixel 等在非线性变换下可能显得拉伸。'),
    },
    {
      title: zh('预览积分'),
      detail: zh('点「预览积分」：全部文件积分并写临时 .npz 缓存，主图显示第一张，结果缩略图可切换。'),
    },
    {
      title: zh('ROI 剖面'),
      detail: zh('切「1D 曲线」标签，勾「框选模式」在热图上拖框（或改 IP/OOP 范围），点「执行1D积分」得面外/面内剖面。'),
    },
    {
      title: zh('导出与出图'),
      detail: zh('「PNG 导出」标签看预览后导出当前或批量全部（选项含标注/字号/DPI/填充/色条/边框/轴反转）；侧栏「导出结果」支持 tiff/edf/npy/hdf5/csv/png，非合并格式只能分别导出。'),
    },
  ],
  outputs: [
    zh('qip×qoop 强度图（tiff/edf/npy/hdf5/csv/png），可再进图像查看器或作图。'),
    zh('ROI 1D 剖面 CSV（面外与面内两套曲线，面内曲线加 (qip) 后缀）。'),
    zh('批量 PNG（带坐标轴/色条/边框，可直接用于报告）。'),
  ],
  pitfalls: [
    zh('「预览积分」积分全部导入文件并写临时缓存；改几何/旋转/覆盖开关会清空结果与缓存并提示重新积分。'),
    zh('导出依赖那次积分生成的缓存：重启应用或改几何后直接导出会报缓存加载失败，必须重新积分。'),
    zh('调色图/对数/对比度会用缓存重载结果，但每次结果刷新都会把 ROI 范围重置为全轴并清空框选——先定显示再框选。'),
    zh('换 ip/oop 单位只清掉 ROI 框，数值范围与热图坐标要重新积分才更新；旧单位下框选会错位。'),
    zh('PNG/图像格式不可合并：只能分别导出或批量到文件夹；web 模式没有保存/目录对话框，导出不可用。'),
  ],
  agentTips: [
    zh('图像选择必须由用户完成，并提醒「只导入要整批处理的图」——预览积分对全部文件生效。'),
    zh('热图上的 ROI 是拖拽框选，canvasX/canvasY 的合成单击只会落一个零面积框，不能可靠代做；highlight「框选模式」并引导用户拖。'),
    zh('预览积分/导出/批量 PNG 都是关键动作，先 confirm；批量导出按文件名写 PNG，同名会覆盖，先确认目录。'),
    zh('缺事实先查 run_task 的 viewer_config：action=probe 读尺寸/帧/通道，action=resolve_geometry_center 校验 .poni；样品方向与角度含义先解释再让用户确认。'),
  ],
}

// ── viewer ───────────────────────────────────────────────────────────────────

const VIEWER_MANUAL: ModuleManual = {
  overview: bi(
    '2D 数据查看器：浏览 EDF/TIFF/H5 单帧与序列，调色图/对数/对比度，按帧或按文件翻页并看缩略图；可导出单帧或批量 PNG。' +
      '开启像素信息模式后点图读 (q, 2θ, χ, I)，还能在图上拖一条线取沿线平均强度剖面。',
    '2D data viewer with colormap/contrast control, frame navigation, thumbnails, PNG export, pixel probing and line profiles.',
  ),
  inputs: [
    zh('2D 图像（.edf/.tif/.tiff/.h5/.hdf5）：可多选、导入文件夹（桌面，可递归）或拖放。'),
    zh('（可选）几何：像素信息与剖面的 q/2θ/χ 需要 .poni 或手动参数；只看图不需要。'),
    zh('（批量导出）输出文件夹：桌面模式下选择，文件名按源文件 basename 生成同名 .png。'),
    zh('（H5）多数据集/4D 多通道时，用侧栏数据集与通道下拉选具体数据。'),
    zh('未知尺寸/帧数可先查 run_task 的 viewer_config（action=probe、filePath）——前提是用户已给文件路径。'),
  ],
  workflow: [
    {
      title: zh('打开文件'),
      detail: zh('侧栏「文件选择」选文件或文件夹/拖放；选替换或追加，确认计数后主区显示图像。'),
    },
    {
      title: zh('H5 数据集'),
      detail: zh('导入 H5 后出现数据集下拉，4D 还有通道下拉；切换会重载当前数据并把帧号归零。'),
    },
    {
      title: zh('调整显示'),
      detail: zh('选色图、对数刻度、预览画质（粗糙=0.25 缩放先出图，100%=全分辨率）；对比度自动或手动，可开色条。'),
    },
    {
      title: zh('浏览帧与文件'),
      detail: zh('多选文件时帧滑杆切文件；单文件多帧时切帧；下方缩略图分页，可开「同步缩略图」按当前显示重渲染。'),
    },
    {
      title: zh('导出 PNG'),
      detail: zh('「PNG 导出」选导出当前帧或批量导出文件夹；DPI 滑杆只影响导出，不影响屏幕预览。'),
    },
    {
      title: zh('像素信息'),
      detail: zh('勾「开启像素信息读取」并填/上传几何；在图上点击读 q、2θ、χ、强度与像素坐标，可开 q 圆环与光斑十字。'),
    },
    {
      title: zh('沿线剖面'),
      detail: zh('仍在像素信息模式下勾「沿线强度剖面」，按住左键在图上拖一条线；设带宽与横坐标（后者需几何），曲线在图下通栏。'),
    },
    {
      title: zh('先退出再导出'),
      detail: zh('PNG 导出与像素信息模式互斥：要导出先关像素信息，要读像素先停下导出。'),
    },
  ],
  outputs: [
    zh('单帧 PNG 或批量 PNG（按源文件同名），用于快速出图与汇报。'),
    zh('屏幕上的像素读数（q/2θ/χ/I）与沿线剖面曲线，用于判断束心、背景、取向或挑窗口；本页不写其它数据文件。'),
  ],
  pitfalls: [
    zh('PNG 导出与像素信息模式互斥：一个开着另一个按钮就禁用，需先关闭。'),
    zh('多选文件时「导出当前帧」导出的是当前文件的第 0 帧（不是屏幕显示帧）；批量导出对 H5 也只取默认数据集第 0 帧。'),
    zh('批量导出按 basename 同名写 PNG，会静默覆盖同目录旧文件；先清理或换输出目录。'),
    zh('自动对比度逐图各自计算，批量图之间颜色不可比；要统一颜色请用「手动」并固定上下限。'),
    zh('未配几何时剖面的 q/2θ/χ 选项被禁用、像素信息也算不出 q；web 模式没有保存/目录对话框，两种 PNG 导出都不可用。'),
  ],
  agentTips: [
    zh('文件/文件夹由用户选择；highlight「选择图像文件」并说明格式，不要代选。'),
    zh('画布点击不可代做读像素：图像是图片加不可点击的叠加层，canvasX/canvasY 的合成点击落不到图像点击处理上，还可能被当成平移或零长划线；请引导用户自己点。'),
    zh('批量导出（写文件、可能覆盖）与切换像素信息模式前先 confirm；导出前提醒关闭像素信息模式。'),
    zh('缺事实先查 run_task 的 viewer_config：action=probe 读尺寸/帧/通道，action=resolve_geometry_center 校验 .poni；不要用截图估 q 或束心。'),
  ],
}

// ── h5-toolkit ───────────────────────────────────────────────────────────────

const H5_TOOLKIT_MANUAL: ModuleManual = {
  overview: bi(
    'H5 格式处理：两个标签共用源目录。格式转换把 H5 内选定数据集批量导出为 TIFF/EDF 图像（非图像数据汇总成 CSV/DAT 表）；' +
      '文件提取按后缀筛出 H5 文件并复制/重命名到一个平铺目录，可处理同名冲突。支持 .h5/.nxs/.hdf5。',
    'H5 toolkit: batch dataset-to-TIFF/EDF/table conversion and suffix-filtered flat file extraction.',
  ),
  inputs: [
    zh('源目录（含 .h5/.nxs/.hdf5）与递归开关（桌面版选文件夹；web 无文件夹对话框）。'),
    zh('转换：输出目录、参考文件后缀（默认 _master，用于挑参考文件与目标文件）。'),
    zh('提取：输出目录、后缀过滤（留空=全部）、是否前置父文件夹名、可选前缀、冲突策略。'),
    zh('转换前先扫描：数据集清单来自参考文件，目标文件按后缀（无匹配时回退全部）。'),
    zh('清单可实时查询：run_task 的 h5convert_scan（sourceDir、refSuffix、recursive）给数据集/目标数，h5_list_files（sourceDir、suffix、recursive）给文件列表——需用户先给目录。'),
  ],
  workflow: [
    {
      title: zh('选源目录'),
      detail: zh('顶部共享区选源目录并决定是否递归；两个标签都用这个目录。'),
    },
    {
      title: zh('设输出与后缀'),
      detail: zh('「格式转换」标签选输出目录、填参考文件后缀（默认 _master），点「扫描并加载」。'),
    },
    {
      title: zh('核对文件清单'),
      detail: zh('扫描后显示 H5 文件表（分页）与汇总：总数/目标文件数/参考文件名；无匹配后缀会明确提示将转换全部。'),
    },
    {
      title: zh('选数据集'),
      detail: zh('按 HDF5 路径分组勾选：≥2 维为图像，0/1 维为表格；4D 可逐通道勾选；默认不勾 instrument 元数据与标量/1D。'),
    },
    {
      title: zh('设格式与命名'),
      detail: zh('选图像 TIFF/EDF 与表格 CSV/DAT；首层文件夹按父文件夹/文件名/数据集命名，可勾「扁平导出」把目录名并进文件名。'),
    },
    {
      title: zh('开始导出'),
      detail: zh('看预计输出文件数后点「开始导出」；进度条与结果摘要给出总数/成功/失败/耗时。'),
    },
    {
      title: zh('扫描待提取'),
      detail: zh('切「文件提取」标签，点「扫描 H5 文件」列出待提取清单（同样可看分页与大小）。'),
    },
    {
      title: zh('设规则并提取'),
      detail: zh('选输出目录、后缀过滤、前置父文件夹、前缀与冲突处理（重命名/跳过/覆盖），点「开始提取」。'),
    },
  ],
  outputs: [
    zh('转换：TIFF/EDF 图像序列（2D 一文件、3D 按帧展开、4D 按帧×通道展开），可被图像查看器/积分模块直接读取。'),
    zh('转换：非图像数据汇总成一个 non_image_data.csv 或 .dat 表。'),
    zh('提取：目标目录里的平铺 H5/NXS 副本（可选父目录名前缀）。'),
  ],
  pitfalls: [
    zh('数据集清单只来自「参考文件」：目标文件若没有该路径会静默跳过（体现在失败数/缺帧），先确认文件结构一致。'),
    zh('「递归扫描」只影响扫描清单与文件列表：转换器与提取器内部始终递归处理源目录，关掉也会处理子文件夹。'),
    zh('转换不检查同名输出，重复运行会覆盖已有 TIFF/EDF；扁平导出下不同子目录的同名文件会互相覆盖。'),
    zh('默认后缀 _master 没有匹配文件时会回退转换全部文件（信息条有警示），别把它当成只转了主文件。'),
    zh('4D 数据集的通道「全不选」表示明确不导出（只有缺省通道配置才回退为全部）；web 模式两个标签都无法使用。'),
  ],
  agentTips: [
    zh('源目录/输出目录必须由用户选择；highlight 文件夹控件并说明要哪种目录，不要代选。'),
    zh('本页无画布交互（canvasX/canvasY 无意义）；可代点标签与扫描，但开始转换/提取会写文件，先 confirm。'),
    zh('缺事实先查 run_task：h5convert_scan（sourceDir、refSuffix、recursive）拿数据集清单与目标数，h5_list_files（sourceDir、suffix、recursive）拿文件列表；扫描前不要断言数量或数据集。'),
    zh('解释扫描信息条时区分「总数/目标文件/参考文件」三个数；无后缀匹配时明确告知会转换全部。'),
  ],
}

// ── png-generate ─────────────────────────────────────────────────────────────

const PNG_GENERATE_MANUAL: ModuleManual = {
  overview: bi(
    '批量 PNG 生成：把源文件夹里的 H5/TIFF/EDF(CBF) 2D 数据按统一显示设置渲染成色图 PNG；' +
      '设置可导出为与图像查看器兼容的 JSON 模板并复用，适合为一批图快速出同风格缩略图或报告图。',
    'Batch PNG rendering of H5/TIFF/EDF(CBF) data with Viewer-compatible JSON templates.',
  ),
  inputs: [
    zh('源文件夹（可递归）与输出文件夹（选源后自动填 源/export，可改）。'),
    zh('文件类型开关：TIFF、EDF/CBF、H5 默认全开。'),
    zh('H5 必须先「扫描文件」把数据集清单填进模板，否则 H5 不产出（模板里没有数据集就直接跳过）。'),
    zh('可选 JSON 模板：导入/拖放恢复设置，导出保存当前设置（与查看器兼容）。'),
    zh('文件计数可用 run_task 的 png_generate（sourceFolder、recursive、scanOnly:true）实时查询——需用户先给源文件夹。'),
  ],
  workflow: [
    {
      title: zh('选文件夹'),
      detail: zh('侧栏「文件夹」选源文件夹，输出自动设为 源/export；按需勾「递归扫描子文件夹」。'),
    },
    {
      title: zh('导入模板'),
      detail: zh('需要复用设置时点「导入 JSON」或把 .json 拖进 JSON 配置区；也可「导出 JSON」保存当前设置。'),
    },
    {
      title: zh('调显示设置'),
      detail: zh('选色图、对数、对比度自动或手动（手动才统一颜色）、输出布局（统一平铺/按文件分目录）、DPI 与色条。'),
    },
    {
      title: zh('扫描文件'),
      detail: zh('点「扫描文件」列出 H5/TIFF/EDF 计数；H5 数据集在此采集，且只在模板还没有数据集时填入。'),
    },
    {
      title: zh('批量导出'),
      detail: zh('点「开始批量导出」，进度条与结果摘要给出总数/成功/失败/耗时；取消时已完成文件保留。'),
    },
    {
      title: zh('核对 JSON'),
      detail: zh('完成后页面显示本次使用的模板 JSON，可复制或导出给下一批复用。'),
    },
  ],
  outputs: [
    zh('输出文件夹中的 PNG：TIFF/EDF 多帧写成 _frameXXXX 后缀；H5 按数据集子目录存放。'),
    zh('模板 JSON（与查看器兼容），可复用或交付给批量流程。'),
  ],
  pitfalls: [
    zh('H5 依赖模板里的数据集清单：不先扫描（或导入的模板数据集为空）时 H5 文件整体跳过，只出 TIFF/EDF 的图。'),
    zh('「自动」对比度逐图各自 min/max，批量图颜色不可比；要统一必须手动填 CLIM。'),
    zh('界面上的「显示坐标轴」不参与渲染：输出是无坐标轴的纯色图；要带坐标轴与标注的出版图请用 GIWAXS 的 PNG 导出。'),
    zh('统一平铺布局下不同子目录的同名文件写同一个 PNG，后者覆盖前者；先改布局或清空输出目录。'),
    zh('注意接口接线：界面提交 sourceFolder/outputFolder/scanOnly，后端 png_generate 只读 source_dir/output_dir 且未见 scanOnly 分支——扫描或运行直接报错时先按此排查，不要归咎于数据。'),
  ],
  agentTips: [
    zh('源/输出文件夹必须由用户选择（web 无文件夹对话框，本页不可用）；highlight 文件夹控件并说明用途，不要代选。'),
    zh('本页无画布交互（canvasX/canvasY 无意义）；可代点「扫描文件」「开始批量导出」，但写文件前先 confirm 并确认输出目录。'),
    zh('缺事实先查 run_task 的 png_generate（sourceFolder、recursive、scanOnly:true）拿各类文件计数，再回答数量或是否为空；不要在扫描前断言。'),
    zh('解释 JSON 模板时说明它与图像查看器同 schema（设置互通），但不包含源/输出文件夹路径。'),
  ],
}

// ── mask-maker ───────────────────────────────────────────────────────────────

const MASK_MAKER_MANUAL: ModuleManual = {
  overview: bi(
    '交互式掩膜编辑：打开一张探测器图，用矩形/圆/椭圆/多边形/线条按「遮盖/擦除」绘制，或按阈值批量遮盖' +
      '（低于/高于/介于/非有限值）；支持撤销/重做/反转/清除，导出 EDF/TIFF/NPY/H5/Fit2D .msk，供积分与标定使用。',
    'Interactive mask editor with shape/threshold tools, undo/redo and EDF/TIFF/NPY/H5/MSK export for integration.',
  ),
  inputs: [
    zh('一张参考图（.edf/.tif/.tiff/.h5/.hdf5；可拖入页面）。'),
    zh('（可选）已有掩膜文件（.edf/.tif/.tiff/.npy/.npz/.msk）加载后继续编辑，尺寸应与图一致。'),
    zh('（导出）保存路径：导出对话框里浏览选择（web 无保存对话框）。'),
    zh('掩膜值为 0/1 两级（single 模式）；画布可用滚轮缩放与平移定位。'),
    zh('图尺寸/帧数可先查 run_task 的 viewer_config（action=probe、filePath）——需用户先给图像路径。'),
  ],
  workflow: [
    {
      title: zh('打开图像'),
      detail: zh('左栏「打开图像」选文件，或把图拖进页面；画布显示原图，右栏出现图像信息与掩膜统计。'),
    },
    {
      title: zh('调显示'),
      detail: zh('右栏显示设置：色图、对数、对比度自动/手动、掩膜显示样式（淡红叠加/纯白填充/深紫轻覆）。'),
    },
    {
      title: zh('选工具与模式'),
      detail: zh('左栏绘制工具选平移/矩形/圆/椭圆/多边形/线条，「绘制模式」选遮盖或擦除。'),
    },
    {
      title: zh('绘制'),
      detail: zh('在画布上拖出图形；矩形在前端即时填充，其它形状提交后端生成；多边形单击加点、双击闭合。'),
    },
    {
      title: zh('阈值遮盖'),
      detail: zh('右栏阈值工具选低于下限/高于上限/介于/非有限值，填数值后应用；只影响命中阈值的像素。'),
    },
    {
      title: zh('编辑核对'),
      detail: zh('撤销/重做（最多 10 步）、反转、清除全部；对照掩膜统计的遮盖像素与比例复核。'),
    },
    {
      title: zh('导出掩膜'),
      detail: zh('左栏「导出 Mask」选格式（EDF/TIFF/NPY/H5/MSK）与保存路径，导出后提示路径。'),
    },
    {
      title: zh('加载已有掩膜'),
      detail: zh('「加载 Mask」选文件；尺寸不一致时按左上角裁/补、不会报错，需自己确认对齐。'),
    },
  ],
  outputs: [
    zh('掩膜文件（EDF/TIFF/NPY/H5/Fit2D .msk），在积分页「掩膜导入」以自定义掩膜引用，或供标定与外部工具使用。'),
    zh('屏幕上的遮盖像素/比例统计，用于判断遮挡是否过度。'),
  ],
  pitfalls: [
    zh('换图会重建掩膜：未导出的编辑直接丢失（只有改显示设置会保留掩膜）。'),
    zh('撤销历史最多 10 步；加载外部掩膜会清空撤销/重做历史。'),
    zh('加载尺寸不同的掩膜不报错，只按左上角裁/补，可能整体错位而不易察觉。'),
    zh('掩膜只有 0/1 两级（不是 silx 多级掩膜）；更复杂的需求请用 pyFAI/silx 生成。'),
    zh('导出需要保存路径；web 模式没有保存对话框，导出按钮无法落地。'),
  ],
  agentTips: [
    zh('图像与掩膜文件必须由用户选择；highlight「打开图像」并说明要哪张图，不要代选。'),
    zh('绘制是拖拽/多点交互：canvasX/canvasY 的合成单击最多落一个多边形顶点或零面积框，不要代画；缩放/撤销/反转可代点，但清除全部属破坏性操作，先 confirm。'),
    zh('导出（写文件）与加载掩膜前先 confirm；提醒换图会丢未导出的掩膜。'),
    zh('缺事实先查 run_task 的 viewer_config（action=probe、filePath）读图尺寸，再判断加载的掩膜是否同尺寸；不要凭缩略图断言遮盖比例。'),
  ],
}

/** Manual registry for the integration / image family. */
export const MANUALS_A: Record<string, ModuleManual> = {
  'integrate-1d': INTEGRATE_1D_MANUAL,
  'integrate-azimuth': INTEGRATE_AZIMUTH_MANUAL,
  'integrate-cake': INTEGRATE_CAKE_MANUAL,
  'integrate-fiber': INTEGRATE_FIBER_MANUAL,
  viewer: VIEWER_MANUAL,
  'h5-toolkit': H5_TOOLKIT_MANUAL,
  'png-generate': PNG_GENERATE_MANUAL,
  'mask-maker': MASK_MAKER_MANUAL,
}
