---
name: xfais-bootstrap
description: |
  One-time self-assembly of the X-FAIS agent bridge: download the MCP server
  from OSS, register it with THIS agent (ZCode / Claude Code / Codex), verify
  the link, then observe and operate the user's running X-FAIS (X-ray
  diffraction/scattering suite, AI build).
  Trigger when the user wants this agent to connect to / control / watch
  X-FAIS, or says 装配/连接 X-FAIS 桥 / connect to X-FAIS / 帮我操作 X-FAIS.
  一次性自主装配 X-FAIS agent 桥：从 OSS 下载 MCP 服务器、登记进本 agent、
  验证连通，之后即可实时观察与操控用户正在运行的 X-FAIS（AI 版）。
---

# X-FAIS 桥自主装配（bootstrap）

前提：用户机器上装有 **X-FAIS-AI**（AI 辅助版，安装包名带 `-AI-`）且正在
运行。桌面版 agent 桥默认开启且只连本机回环，**无需设置任何环境变量**。
普通版（无 -AI-）没有桥，list_instances 列不出来属正常。

## 1. 下载服务器脚本（固定名 = 永远最新）

- 下载 `https://xfais.oss-cn-beijing.aliyuncs.com/xfais-mcp-latest.py`，
  保存为 `~/.xfais/mcp/mcp_server.py`（目录不存在则先创建）。
- 版本核对：脚本头部 `SERVER_INFO` 的 version 应 ≥ 用户 X-FAIS 版本。
- **先落盘、再登记**——绝不执行「下载即运行」的管道命令。
- 运行要求：Python ≥ 3.9，仅标准库，无需 pip 安装任何依赖。

## 2. 登记 MCP（按本 agent 类型选一）

**ZCode**（设置 → MCP 服务器，或对应配置文件）：

```json
{
  "mcpServers": {
    "xfais": { "command": "python", "args": ["<绝对路径>/mcp_server.py"] }
  }
}
```

**Claude Code**（终端一条命令）：

```bash
claude mcp add xfais -- python "<绝对路径>/mcp_server.py"
```

**Codex**（`~/.codex/config.toml`）：

```toml
[mcp_servers.xfais]
command = "python"
args = ["<绝对路径>/mcp_server.py"]
```

**WorkBuddy**（若不支持 MCP）：走 HTTP 直连退化模式——把同目录的
`../SKILL.md`（HTTP 端点文档）复制进 WorkBuddy 的 skills 目录，
按文档直接 `POST http://127.0.0.1:<port>/api/agent_command`。

远程/Web 部署（可选，运维动作）：部署侧开 `XFAIS_AGENT_BRIDGE=1`；agent 侧
设 `XFAIS_AGENT_TARGETS=https://<部署地址>`（精确匹配，未配置的内网地址会被
拒绝）；部署设了 `XFAIS_AGENT_TOKEN` 时本地设同值。

## 3. 验证

新开会话（或重载 MCP 配置）后调用 `xfais_list_instances`——应列出用户正在
运行的 X-FAIS-AI 窗口（url / pid / 当前页面 / 版本）。多窗口时每个一条，
按 pid 和当前页面区分；后续每个工具调用用 `url` 参数指定目标实例。

## 4. 使用守则

- 动手前先 `xfais_get_state`；多窗口先 `xfais_list_instances`。
- **态势自回传**：每次工具返回末尾都带「态势」行（当前页面/工作区摘要/教程
  位置与下一步）——先读它再行动，能省掉大量重复 `get_state` 的 token。
- **教学优先（缺信息时先教后做）**：不确定下一步、或觉得缺乏上下文时，先读
  该模块的**详细说明**（`xfais_get_modules route=<routeName>`，含概述/前提/
  真实流程/产出/坑点/给 agent 的提示），然后向用户**解释**并 `xfais_highlight`
  对应控件，让用户自己完成文件选择等私人操作——而不是盲目点击试探。只有
  用户明确要求代做、或动作安全（查询/加载）时才代替点击；运行/导出/覆盖
  等关键动作必须 `xfais_confirm`。
- **金律（反幻觉）**：在未调用 `xfais_get_modules`（全模块目录 + 能力卡）并对
  相关事实执行其 liveQueries 配方之前，**禁止声称"X-FAIS 没有某功能/某数据/
  某标样"**。标样、探测器、空间群、支持格式等清单都能 `xfais_run_task` 实时
  查询，且**因机器而异**——用户可自行添加 `*_custom` 自定义标样，任何文档示例
  （包括本文件）对清单内容的断言一律不作数，只有查询结果算数。经查询
  确认缺失时才走生成/上传：相关模块可**生成**（如 `cell-calibrant-generator`
  按晶胞参数生成 .D，再在标定向导「标样文件 → 本地上传」使用），或让用户
  本地上传。路由不确定时先查目录关键词（每模块带中英关键词）。
- 读图判断（光斑中心/衍射环/曲线形态）用 `xfais_screenshot`，返回图片可
  直接视觉判读；坐标点击用 get_state 返回的 cssWidth/cssHeight 换算。
- **关键操作（长任务/导出/覆盖数据）必须先 `xfais_confirm`**，用户在应用内
  点「确认」后才继续。
- **复杂任务必须问用户（应用侧强制门禁，2026-11-01）**：`xfais_run_task` 调
  `calibration` 的 set_center/refine/ring_standard 或任何
  `transmission` 任务时，应用返回 `code=need_user_input`（附问题清单与
  `confirm_nonce`）。此时必须：① `xfais_confirm` 转述问题清单并带
  `confirmNonce` 提问 → ② 用户点「确认」激活令牌 → ③ 重试并在 params 加
  `"_agent_confirm": "<nonce>"`。**PONI 快速通道**：用户已提供 .poni 时在
  params 带 `poni_path=<绝对路径>`——标定的几何类问题自动豁免（先经未门禁的
  `calibration seed_from_poni` 载入），只剩标样与图像仍需确认。
  禁止凭猜测补齐标样/探测器/波长/距离等
  实验信息，禁止绕过门禁。
- **批量计算走本地 CLI**：实例注册表带 `python`（捆绑解释器）与 `cli`
  （pyFAI 风格命令行）路径，`xfais_run_cli` 或自己的 shell 都能跑
  `info / poni / average / integrate / bgsubtract / transmission /
  lamellar / orientation`——大文件批量积分、背景扣除等优先走 CLI，
  界面操作留给需要人眼判断的步骤。
- 文件/文件夹较多时：与用户约定统一工作目录（如 `D:\xfais-work`），集中
  收拢后经 `xfais_run_task` 或 `xfais_run_cli` 以该目录路径批量处理；界面
  加载则引导用户一次选中该目录（highlight 目标按钮，文件选择对话框留给用户）。
- 操作完不要关闭 X-FAIS——桥是常驻的，用户继续用。
