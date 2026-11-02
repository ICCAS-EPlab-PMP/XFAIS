---
name: xfais-agent
description: |
  Operate a running X-FAIS (X-ray diffraction/scattering suite, AI build) instance
  over its agent bridge. Use when the user asks you to check/control X-FAIS: see
  which page it is on, read the current canvas (beam centre, rings, fitted curves),
  click buttons or image coordinates, spotlight controls for the user, ask in-app
  confirmation before key actions, or run backend tasks (integration, calibration,
  curve fitting). Works for local desktop instances (auto-discovered) and
  operator-configured web deployments.
---

# X-FAIS Agent 桥（无 MCP 时的 HTTP 直连版）

X-FAIS（AI 版）内置 agent 桥。若宿主不支持 MCP，直接按本文件用 HTTP 调用。

## 前提

- 本机有正在运行的 X-FAIS（AI 版）；实例信息在 `~/.xfais/instances/*.json`
  （字段 `url`/`pid`/`route`/`ai`）。多开时逐个读文件区分。
- Web 部署需运维开启（`XFAIS_AGENT_BRIDGE=1`），URL 由用户提供。

## 端点（base = 实例 url，如 `http://127.0.0.1:port`）

```
POST /api/agent_command   {"command": "<cmd>", "payload": {...}, "timeout_ms": 20000}
POST /api/agent_task      {"command": "<task>", "params": {...}, "timeout_s": 120}
```

命令白名单（command 取值）：

| command | payload | 说明 |
|---|---|---|
| `state` | `{}` | 当前页面/画布尺寸/各模块快照/PONI 路径/教程进度通报（+`hasManual` 指针） |
| `guide` | `{route?}` | 模块分步教程（done 实时求值=用户当前位置，anchorPresent/enabled=控件可操作性）+ 能力卡 |
| `modules` | `{route?}` | 全模块目录（用途+关键词+金律）；带 route 返回该模块**完整卡：能力 + 详细说明（概述/前提/流程/产出/坑点/agent 提示）** |
| `capture` | `{canvas?, maxWidth?}` | 画布 PNG（base64 返回） |
| `click` | `{target: {aiId? / testId? / text? / canvas: {x,y}, canvasIndex?}}` | 点击控件/画布坐标 |
| `highlight` | `{aiId, note?}` | 聚光控件 |
| `confirm` | `{message, aiId?, note?, confirm_nonce?}` | 应用内确认弹窗（阻塞至用户点击）；**门禁任务必经之路**：带 `confirm_nonce` 提问，用户确认后令牌激活 |
| `navigate` | `{path}` | 站内导航（回复即新页面的完整 state） |
| `apply_options` | `{routeName, options}` | 预选模块选项 |

**态势回传**：除 `state`（本身即全量）与 `navigate`（回复即新 state）外，每个命令
的回复 `data.context` 都带当前态势——`route`（页面）+ `snapshot`（filesCount/
hasPoni/canRun/phase/extras）+ `guide`（教程位置与下一步）。先读态势再决定下一步，
省掉补查 state 的往返。

任务名（agent_task 的 command）：`integrate1d`、`integrate_azimuth`、
`integrate_cake`、`integrate_fiber`、`calibration`、`curve_fitting`、
`orientation_analysis`、`lamellar_analysis`、`bg_subtract`、`mask_builder` 等
（与 UI 相同的命令名）。

## 复杂任务门禁（硬规则，2026-11-01）

`calibration` 的 `set_center` / `refine` / `ring_standard` 与
**全部** `transmission` 任务由应用侧强制拦截：`agent_task` 直接返回
`code=need_user_input`，附 `questions`（必须向用户确认的问题）、`why` 与
一次性 `confirm_nonce`。强制流程：

1. 调 `confirm` 命令：`message` 完整转述 questions + 你的执行计划，
   payload 带 `confirm_nonce`；
2. 用户在应用内点「确认」→ 令牌激活（10 分钟内有效，单次使用）；
3. 重发 `agent_task`，`params` 里加 `"_agent_confirm": "<nonce>"`。

**PONI 快速通道**：用户已提供 .poni 时，`params` 带上
`"poni_path": "<绝对路径>"`（或 `poniPath`）——标定的几何类问题
（探测器/波长/距离/光束中心）自动豁免（应答里 `poni_accepted: true`、
问题只剩标样与图像两项）。执行前先经未门禁的 `calibration seed_from_poni`
把 PONI 载入会话。无效路径/非 .poni 不放宽门禁；transmission 门禁不受
PONI 影响。

禁止：未经用户确认重试；凭记忆/猜测补齐缺失实验信息；换命令或换路由绕过。
真人经 UI 操作不走这条链路，不受门禁影响。

## 本地 CLI（批量计算免 UI，2026-11-01）

实例注册文件（`~/.xfais/instances/*.json`）自本版起带 `python`（捆绑解释器
绝对路径）与 `cli`（`python/xfais_cli.py` 绝对路径）字段。用它们直接在
本机跑 pyFAI 风格命令行（无需 UI 往返）：

```
<python> <cli> info "D:/data/*.edf"
<python> <cli> poni geometry.poni
<python> <cli> average -o avg.edf -m median "D:/bg/*.tif"
<python> <cli> integrate -p g.poni -n 2048 --unit q_nm^-1 "D:/data/*.edf"
<python> <cli> bgsubtract -b bg.edf --ion-folder D:/ion -o D:/out "D:/data/*.edf"
<python> <cli> transmission --region rect:400,400,480,480 --reference first D:/db/*.edf
<python> <cli> lamellar curve.txt --json
<python> <cli> orientation chi_i.txt --method both --json
<python> <cli> version
```

每个子命令 `--help` 有双语说明；`--json` 输出机器可读。写输出文件时选用户
能找到的目录；长任务先 `confirm`。

## 行为守则

1. 动手前先 `state`；多开先读注册目录区分实例。
2. **教学优先**：缺信息/不确定下一步时，先教后做——读该模块详细说明
   （`modules` 带 `route`）、向用户解释并 `highlight` 对应控件，让用户自己
   完成文件选择等操作；只有用户明确要求代做、或动作安全（查询/加载）时才
   代替点击。
3. **金律（反幻觉）**：断言"X-FAIS 没有某功能/某数据/某标样"之前，必须先查
   模块目录与能力卡里的实时查询配方（标样/探测器/空间群等清单均可
   `agent_task` 实时查询，且因机器而异）；确认缺失时走生成（如晶胞参数生成
   .D）或让用户本地上传。
4. 读图判断（光斑中心/环位/曲线形态）用 `capture`，坐标用 `state` 返回的
   cssWidth/cssHeight 换算。
5. **关键操作（运行长任务、导出、覆盖数据）必须先 `confirm`**，用户确认后再执行。
6. **复杂任务必须问用户**：`agent_task` 返回 `code=need_user_input` 时按上文
   门禁流程走，拿不到用户确认不得执行，也不得猜测缺失的实验信息。
7. 操作完不要关闭应用——桥是常驻的，用户继续用。
