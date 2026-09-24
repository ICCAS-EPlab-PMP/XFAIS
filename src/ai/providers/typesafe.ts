/**
 * typesafe.ts — Jev (TypeSafe AI "System One Model") adapter.
 *
 * Docs: docs.typesafe.ai (schema verified against the live API 2026-09-23):
 *   POST /v1/systemone
 *   { state, model, questions: { <id>: { type:'choice', instructions,
 *     criteria: { option: description|null } } } }
 *   → { answers: { <id>: { choice, confidence, probabilities } } }
 * Every URL and field name lives in THIS FILE ONLY so a remote change is a
 * one-file fix.
 *
 * No network is touched at import time; only `askTypesafeChoice` performs a
 * request (via the main-process proxy — the API sends no CORS headers). All
 * failures surface as `AiProviderError` with a stable code so the agent chain
 * can fall through to the rules router.
 */

import { AiProviderError, type ChoiceAnswer, type ChoiceQuestion } from '../types'

// ── Endpoint / payload constants (single source of truth) ─────────────────────

const ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
const MODEL_ID = 'jev-latest'
const TIMEOUT_MS = 12_000

// ── Small defensive-parsing helpers ───────────────────────────────────────────

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

const asString = (v: unknown): string | undefined =>
  typeof v === 'string' && v.length > 0 ? v : undefined

const asFiniteNumber = (v: unknown): number | undefined =>
  typeof v === 'number' && Number.isFinite(v) ? v : undefined

/** Pull `answers.<id>` out of the API envelope (a dict keyed by our ids). */
function extractAnswer(data: unknown, id: string): Record<string, unknown> {
  if (!isRecord(data)) return {}
  const answers = isRecord(data.answers) ? data.answers : {}
  const answer = answers[id]
  return isRecord(answer) ? answer : {}
}

/** Accept `probabilities` / `probs` / `distribution` maps; keep valid entries. */
function extractProbabilities(result: Record<string, unknown>): Record<string, number> | undefined {
  const raw =
    isRecord(result.probabilities) ? result.probabilities
    : isRecord(result.probs) ? result.probs
    : isRecord(result.distribution) ? result.distribution
    : undefined
  if (!raw) return undefined

  const out: Record<string, number> = {}
  let sum = 0
  for (const [key, value] of Object.entries(raw)) {
    const n = asFiniteNumber(value)
    if (n !== undefined && n >= 0) {
      out[key] = n
      sum += n
    }
  }
  if (Object.keys(out).length === 0) return undefined
  // Normalize to sum 1 (tolerates raw counts or already-normalized maps).
  if (sum > 0) {
    for (const key of Object.keys(out)) out[key] = out[key] / sum
  }
  return out
}

/** Normalize any number into a clamped 0..1 confidence. */
function clamp01(v: unknown, fallback = 0.5): number {
  const n = asFiniteNumber(v)
  if (n === undefined) return fallback
  return Math.min(1, Math.max(0, n))
}

// ── Public API ────────────────────────────────────────────────────────────────

interface PostResult {
  ok: boolean
  status: number
  data: unknown
}

/**
 * POST JSON to the endpoint. In the desktop app this goes through the
 * main-process IPC proxy (api.typesafe.ai sends no CORS headers, so a
 * renderer fetch() is ALWAYS blocked there); web mode falls back to fetch.
 */
async function postJson(
  body: Record<string, unknown>,
  apiKey: string
): Promise<PostResult> {
  const payload = {
    url: ENDPOINT,
    headers: { Authorization: `Bearer ${apiKey}` },
    body,
  }
  const proxy = typeof window !== 'undefined' ? window.desktop?.net?.postJson : undefined
  if (typeof proxy === 'function') {
    // Timeout enforced in the main process (15 s).
    return await proxy(payload)
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(ENDPOINT, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    })
  } catch (err) {
    const message = err instanceof DOMException && err.name === 'AbortError'
      ? `Jev request timed out after ${TIMEOUT_MS / 1000}s.`
      : `Jev network request failed: ${err instanceof Error ? err.message : String(err)}`
    throw new AiProviderError('network', message)
  } finally {
    clearTimeout(timer)
  }
  let data: unknown
  try {
    data = await response.json()
  } catch {
    data = undefined
  }
  return { ok: response.ok, status: response.status, data }
}

/** Build the criteria map for one question (null descriptors allowed). */
function criteriaMap(q: ChoiceQuestion): Record<string, string | null> {
  return Object.fromEntries(q.choices.map((c) => [c, q.criteria?.[c] ?? null]))
}

/**
 * Ask Jev several choice questions in ONE request (the API carries a
 * `questions` dict; template + unit are asked together so the internal
 * judgement stays a single round trip).
 * 一次请求携带多个 choice 问题（API 的 questions 为字典；模板+单位同问，
 * 内部判断单次往返完成）。
 */
export async function askTypesafeChoices(
  questions: ChoiceQuestion[],
  apiKey: string
): Promise<ChoiceAnswer[]> {
  const key = typeof apiKey === 'string' ? apiKey.trim() : ''
  if (!key) {
    throw new AiProviderError('no_key', 'Jev (TypeSafe) API key is missing — add it in Settings.')
  }
  if (questions.length === 0) return []

  // All questions share one `state`; callers pass the same context object.
  // 多个问题共享同一 state；调用方传入同一份上下文。
  const state = questions[0].state ?? {}
  const questionsPayload: Record<string, unknown> = {}
  for (const q of questions) {
    questionsPayload[q.id] = {
      type: 'choice',
      instructions: q.instructions,
      criteria: criteriaMap(q),
    }
  }

  let result: PostResult
  try {
    result = await postJson(
      {
        state,
        model: MODEL_ID,
        questions: questionsPayload,
      },
      key
    )
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    throw new AiProviderError('network', `Jev network request failed: ${message}`)
  }

  if (result.status === 401 || result.status === 403) {
    throw new AiProviderError('no_key', `Jev rejected the API key (HTTP ${result.status}).`)
  }
  if (!result.ok) {
    throw new AiProviderError(
      'network',
      `Jev endpoint returned HTTP ${result.status}.`
    )
  }

  return questions.map((q) => {
    const questionResult = extractAnswer(result.data, q.id)

    const choice =
      asString(questionResult.choice) ??
      asString(questionResult.top_choice) ??
      asString(questionResult.selected)

    if (!choice) {
      throw new AiProviderError(
        'bad_response',
        `Jev response did not contain a recognizable choice field for question '${q.id}'.`
      )
    }

    const probabilities = extractProbabilities(questionResult)
    const confidence =
      asFiniteNumber(questionResult.confidence) ??
      asFiniteNumber(questionResult.probability) ??
      probabilities?.[choice]

    return {
      id: asString(questionResult.id) ?? q.id,
      choice,
      confidence: clamp01(confidence, probabilities?.[choice] ?? 0.5),
      probabilities,
    }
  })
}

/**
 * Ask Jev a single choice question. See `askTypesafeChoices` for the batch
 * form used by the internal (in-module) judgements.
 */
export async function askTypesafeChoice(
  q: ChoiceQuestion,
  apiKey: string
): Promise<ChoiceAnswer> {
  return (await askTypesafeChoices([q], apiKey))[0]
}
