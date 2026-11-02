/**
 * agent-bridge-e2e.mjs — v0.3.5 agent bridge end-to-end (web mode).
 *
 * Real chain: Playwright page (renderer agentLink WS) ⇄ serve_web AgentBridge
 * ⇄ this script driving HTTP POST /api/agent_command. Verifies state /
 * navigate / click / highlight / confirm (modal round-trip!) and capture,
 * plus the instance registry file. Run against a live server started with
 * XFAIS_AGENT_BRIDGE=1. Node ≥ 18 (global fetch).
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.XFAIS_E2E_URL ?? 'http://127.0.0.1:18799'
let failures = 0
const check = (name, cond, extra = '') => {
  const ok = !!cond
  if (!ok) failures += 1
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ` — ${extra}` : ''}`)
}

async function agentCommand(command, payload = {}, timeoutMs = 15000) {
  const resp = await fetch(`${BASE}/api/agent_command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command, payload, timeout_ms: timeoutMs }),
  })
  return resp.json()
}

const browser = await chromium.launch()
const page = await browser.newPage()
const pageErrors = []
page.on('pageerror', (err) => pageErrors.push(String(err)))

await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000) // agent link WS connect + hello

// 1. state — route should be home, AI build marker present
const state = await agentCommand('state')
check('state ok', state.ok === true, JSON.stringify(state).slice(0, 120))
check('state route=home', state.data?.route?.name === 'home')
check('state ai=true', state.data?.ai === true)
check('state version 0.3.5', state.data?.version === '0.3.5')

// 2. click — cite button via aiId (window.open is harmless in headless)
const click = await agentCommand('click', { target: { aiId: 'home:cite-pyfai' } })
check('click aiId', click.ok === true && click.data?.clicked === true, JSON.stringify(click).slice(0, 100))
// 2026-10-27: every reply carries the situation context (route + snapshot digest + guide)
const ctx = click.data?.context
check(
  'click reply carries situation context',
  ctx && ctx.route?.name === 'home' && 'guide' in ctx,
  JSON.stringify(ctx).slice(0, 140)
)

// 2b. modules — full card includes the detailed manual (workflow grounded)
const modsCard = await agentCommand('modules', { route: 'calibration' })
const manual = modsCard.data?.module?.manual
check(
  'modules route card has detailed manual',
  manual && Array.isArray(manual.workflow) && manual.workflow.length >= 4 && manual.overview?.length > 20,
  `workflow=${manual?.workflow?.length} pitfalls=${manual?.pitfalls?.length}`
)

// 3. click — text match fallback (AI build hides the normal 检测更新 button by
// design, 2026-10-26: updates go through the AI channel; click that one)
const clickText = await agentCommand('click', { target: { text: '检查AI辅助版' } })
check('click by text', clickText.ok === true, JSON.stringify(clickText).slice(0, 100))

// 4. highlight — known anchor on home
const hl = await agentCommand('highlight', { aiId: 'home:cite-pyfai', note: 'E2E' })
check('highlight ok', hl.ok === true && hl.data?.ok === true)

// 5. navigate — to calibration
const nav = await agentCommand('navigate', { path: '/workspace/calibration' })
check('navigate calibration', nav.ok === true && nav.data?.route?.name === 'calibration')
check('navigate state hasManual pointer', nav.data?.hasManual === true, String(nav.data?.hasManual))
check('navigate state has guide briefing', 'guide' in (nav.data ?? {}))

// 6. apply_options — calibration mode via module vocabulary
const apply = await agentCommand('apply_options', { routeName: 'calibration', options: { mode: 'com' } })
check('apply_options dispatched', apply.ok === true && apply.data?.dispatched === true)
await page.waitForTimeout(300)
const modeActive = await page.evaluate(() => {
  const btn = document.querySelector('[data-ai-id="calibration:mode-com"]')
  return btn?.className?.includes('active') ?? false
})
check('apply_options set com mode on UI', modeActive === true)

// 7. capture — whatever the calibration page holds; must not crash the link
const cap = await agentCommand('capture', { maxWidth: 600 })
check('capture handled', cap.ok === true || /no canvas/.test(String(cap.error)), JSON.stringify(cap).slice(0, 90))

// 8. confirm — full modal round trip: send, user clicks 确认, result returns
const confirmPromise = agentCommand('confirm', { message: 'E2E：确认执行测试操作？', timeout_s: 20 }, 25000)
await page.waitForSelector('[data-ai-id="agent:confirm-ok"]', { timeout: 8000 })
await page.click('[data-ai-id="agent:confirm-ok"]')
const confirmResult = await confirmPromise
check('confirm user-confirmed', confirmResult.ok === true && confirmResult.data?.confirmed === true, JSON.stringify(confirmResult).slice(0, 100))

// 9. cancel path — user clicks 取消
const cancelPromise = agentCommand('confirm', { message: 'E2E：这次请点取消' }, 25000)
await page.waitForSelector('button.agc-btn--cancel', { timeout: 8000 })
await page.click('button.agc-btn--cancel')
const cancelResult = await cancelPromise
check('confirm user-cancelled', cancelResult.ok === true && cancelResult.data?.confirmed === false)

// 10. agent_task — run a real backend task through the sink (list_space_groups: fast, no files)
const task = await fetch(`${BASE}/api/agent_task`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ command: 'list_space_groups', params: {}, timeout_s: 60 }),
}).then((r) => r.json())
check('agent_task ok', task.ok === true, JSON.stringify(task).slice(0, 120))

// 11. instance registry file exists and reflects the live route
await page.waitForTimeout(400)
const regDir = join(homedir(), '.xfais', 'instances')
let registryOk = false
let registryInfo = null
try {
  const { readdirSync } = await import('node:fs')
  for (const f of readdirSync(regDir)) {
    if (!f.endsWith('.json')) continue
    const info = JSON.parse(readFileSync(join(regDir, f), 'utf-8'))
    if (info.url === BASE || info.httpPort === 18799) {
      registryInfo = info
      registryOk = info.route === 'calibration' && info.ai === true
    }
  }
} catch (err) {
  console.log('registry read error:', String(err))
}
check('registry file live (route=calibration, ai)', registryOk, JSON.stringify(registryInfo).slice(0, 140))

// 12. no page errors through the whole run
check('zero pageerror', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | ').slice(0, 160))

await browser.close()
console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILURES`)
process.exit(failures === 0 ? 0 : 1)
