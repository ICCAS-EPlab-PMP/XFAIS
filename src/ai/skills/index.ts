/**
 * skills/index.ts — Distilled workflow knowledge for LLM prompts.
 *
 * The markdown files are plain documentation; Vite's `?raw` imports inline
 * their text at build time (no runtime file reads).
 */

import waxs from './waxs.md?raw'
import saxs from './saxs.md?raw'
import calibration from './calibration.md?raw'

/** Skill documents keyed by topic ('waxs' | 'saxs' | 'calibration'). */
export const SKILL_TEXT: Record<string, string> = {
  waxs,
  saxs,
  calibration,
}
