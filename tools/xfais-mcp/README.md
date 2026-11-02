# xfais-mcp — X-FAIS agent 桥（MCP 服务器）

让 ZCode / Claude Code / Codex / WorkBuddy 等支持 MCP 的 AI agent **实时观察和操作一个正在运行的 X-FAIS（AI 版）实例**：

- 实例发现（多开时按 pid/端口/当前页面区分谁是谁）；
- 实时状态 + **画布截图（MCP image 内容，视觉模型可直接读图**——判断光斑中心、衍射环、拟合曲线）；
- **点击按钮 / 点击图像坐标**（引导点拾取、放峰等画布交互）；
- 高亮聚光控件、应用内**确认弹窗**（关键操作必须由用户点击确认）；
- 页面导航、模块选项预选（复用 X-FAIS 决策模型的词汇表）；
- 直接运行后端任务（积分/标定/拟合等，与 UI 同一条处理链）；
- **复杂任务强制提问门禁**（2026-11-01）：光斑中心查找、几何精修、透过率测量
  等依赖用户实验数据的任务，agent **必须**先经应用内确认弹窗向用户提问、
  用户点「确认」后才能执行（一次性令牌，应用侧强制，UI 真人操作不受影响）；
- **pyFAI 风格本地 CLI**（2026-11-01）：`xfais_run_cli` 用实例自带的 Python
  运行时直接跑 `info / poni / average / integrate / bgsubtract / transmission /
  lamellar / orientation` 等批量计算命令，不经 UI 往返。

Agent 操作**不会关闭或重启实例**——命令走常驻链路，一次工具调用一次操作。

零依赖：仅 Python ≥ 3.9 标准库。

## 安全模型

- 仅 http/https；**禁止重定向**；链路本地/保留地址一律阻断。
- **回环地址（127.0.0.1 本机实例）始终允许**——这正是本地桥的目标。
- 非回环目标（Web 部署）**必须由运维在环境变量里精确配置**，agent 无法把服务器指向任意内网地址。
- 桌面版默认开启（仅绑回环）；Web 部署默认关闭，需 `XFAIS_AGENT_BRIDGE=1`。
- 可选共享令牌：部署侧 `XFAIS_AGENT_TOKEN`，agent 侧同环境变量。

## 环境变量

| 变量 | 作用 |
|---|---|
| `XFAIS_AGENT_TARGETS` | 逗号分隔的远程/Web 部署 base URL（本地实例自动发现，无需配置） |
| `XFAIS_AGENT_TOKEN` | 部署设置了令牌时填同一值 |

## 分发与自主装配（推荐路径）

MCP 服务器经 OSS 分发，agent 读到装配 skill 后自己完成下载+登记：

1. 发版时上传两个文件到 OSS（桶根，同名覆盖即更新）：
   - `tools/xfais-mcp/mcp_server.py` → 上传为 **`xfais-mcp-latest.py`**
   - `tools/xfais-mcp/bootstrap/SKILL.md` → 上传为 **`xfais-bootstrap-skill.md`**
2. 用户对任意 agent 说「按 https://xfais.oss-cn-beijing.aliyuncs.com/
   xfais-bootstrap-skill.md 装配 X-FAIS 桥」——agent 读取该文档，自行下载
   `xfais-mcp-latest.py` 到 `~/.xfais/mcp/`、登记进自己的 MCP 配置、调
   `xfais_list_instances` 验证。全程无需用户手工改配置。

## 四端接入配置

以下 `PATH` 替换为本目录绝对路径。

### Claude Code

`claude mcp add xfais -- python PATH/mcp_server.py`，或编辑配置：

```json
{
  "mcpServers": {
    "xfais": { "command": "python", "args": ["PATH/mcp_server.py"] }
  }
}
```

### ZCode

设置 → MCP 服务器，添加：

```json
{
  "mcpServers": {
    "xfais": { "command": "python", "args": ["PATH/mcp_server.py"] }
  }
}
```

### Codex

`~/.codex/config.toml`：

```toml
[mcp_servers.xfais]
command = "python"
args = ["PATH/mcp_server.py"]
```

### WorkBuddy

若支持 MCP，同上配置；否则退化为 SKILL.md 形态（见本目录 `SKILL.md`，
agent 直接按文档用 HTTP 调 `/api/agent_command` 等）。

## 工具一览

**每个工具的返回末尾都带「态势」行**（当前页面 / 工作区摘要 / 教程位置与下一步）——
先读态势再决定下一步，省掉反复 `get_state` 的 token 消耗。

**教学优先**：缺信息/不确定下一步时，先教后做——读模块详细说明
（`xfais_get_modules route=<名>`）、向用户解释并 `xfais_highlight` 对应控件，
让用户自己完成文件选择等操作；只有用户明确要求代做、或动作安全（查询/加载）
时才代替点击；关键动作（运行/导出/覆盖）必须 `xfais_confirm`。

**复杂任务门禁（硬规则）**：`calibration` 的 set_center / refine /
ring_standard 与**全部** `transmission` 任务由应用侧强制拦截——
`xfais_run_task` 返回 `code=need_user_input` 时，agent 必须按返回的问题清单
调 `xfais_confirm`（带 `confirmNonce`）向用户提问，用户点「确认」激活令牌后，
再以 `params._agent_confirm=<nonce>` 重试。**禁止**凭猜测补齐缺失信息、
未经确认重试、或换命令绕过。
**PONI 快速通道**：用户已提供 .poni 时，把绝对路径放进 `params.poni_path`
（或 `poniPath`）——标定的几何类问题（探测器/波长/距离/光束中心）自动豁免，
只剩标样与图像两项仍需确认；执行前先经未门禁的 `calibration seed_from_poni`
把 PONI 载入会话。transmission 门禁不受 PONI 影响（PONI 回答不了光斑区域）。

| 工具 | 说明 |
|---|---|
| `xfais_list_instances` | 列出本机运行中的 X-FAIS（pid/端口/页面/AI 标记），多开时先调它 |
| `xfais_get_state` | 当前页面、语言、版本、画布尺寸（供坐标点击）、**当前模块工作区摘要**、PONI 路径、**教程进度通报**（用户在第几步 + 下一步）、`hasManual` 指针。输出默认紧凑文本（`verbose=true` 才回传完整 JSON）。对接后第一个调它 |
| `xfais_get_modules` | **全模块目录**（每个模块的用途 + 路由关键词，回答"这事该去哪个模块"）；带 `route` 时返回该模块**完整卡**：**详细说明**（概述/前提/真实流程/产出/坑点/给 agent 的教学提示——操作前必读）、能力速览、**可实时查询的事实配方**（标样/探测器/空间群清单等——查了再说，禁止凭记忆断言"没有"）、干不了时去哪。**金律一（反幻觉）：断言"X-FAIS 不支持 X"之前必须先查这里并执行相关查询；金律二（教学优先）：不确定就先教后做** |
| `xfais_get_guide` | 当前模块的**内部教程 + 能力卡**：有序步骤、每步控件干啥、done 实时求值（=用户当前位置，可能已点过几步）、anchorPresent/enabled（该控件此刻是否在 DOM/是否灰度）；末尾附**说明摘要**（全文走 get_modules）。操作不熟悉的模块前先调它；`route` 参数可取其它模块的教程 |
| `xfais_screenshot` | 截取当前主画布 PNG（image 内容，视觉可读），末尾附态势行 |
| `xfais_click` | 点控件（aiId/testId/可见文字）或画布坐标（canvasX/canvasY，CSS 像素）；失败时提示先读态势/教程解释，不要重试刷运气。末尾附态势行 |
| `xfais_highlight` | 聚光控件引导用户（非阻塞），配一句解释更好教。末尾附态势行 |
| `xfais_confirm` | 应用内确认弹窗，阻塞到用户点确认/取消（关键操作必走；**门禁任务的必经之路**——带 `confirmNonce` 提问，确认后令牌激活）。末尾附态势行 |
| `xfais_navigate` | 站内导航（如 `/workspace/calibration`），回复即新页面的工作区摘要 + 教程位置 |
| `xfais_apply_options` | 预选模块选项（calibration 三模式 / orientation 方法等）；末尾态势行可核对是否生效 |
| `xfais_run_task` | 运行后端任务（integrate1d / calibration / curve_fitting …）；**复杂任务被门禁拦截时返回 need_user_input + 问题清单 + confirm_nonce**；成功后自动补一次 state，末尾附新鲜态势 |
| `xfais_run_cli` | 本机直接跑 X-FAIS 捆绑的 pyFAI 风格 CLI（解释器与脚本路径来自实例注册表）：`info / poni / average / integrate / bgsubtract / transmission / lamellar / orientation / version`，`args` 为原始 CLI 参数数组（通配符由 CLI 自行展开），适合批量计算、不经 UI |

## 典型用法（agent 侧提示词示例）

```
看一下现在 X-FAIS 在哪个页面（list_instances + get_state）。
帮我判断直通光的光斑中心：screenshot 截图 → 读图给出中心坐标 →
click 画布坐标点选中心 → highlight "calibration:load" 引导我确认。
```
