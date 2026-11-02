/**
 * Global undo/redo stack (command pattern).
 * Commands are user-operation-granular: place/remove peak, param edits,
 * point exclusion, fit commit, smooth commit, auto-detect, baseline edits.
 */
import { computed, ref } from 'vue'

export interface Command {
  label: string
  undo(): void
  redo(): void
}

const MAX_DEPTH = 100

const undoStack = ref<Command[]>([])
const redoStack = ref<Command[]>([])

export const canUndo = computed(() => undoStack.value.length > 0)
export const canRedo = computed(() => redoStack.value.length > 0)

export function pushCommand(cmd: Command): void {
  undoStack.value.push(cmd)
  if (undoStack.value.length > MAX_DEPTH) undoStack.value.shift()
  redoStack.value.length = 0
}

export function undo(): Command | null {
  const cmd = undoStack.value.pop()
  if (!cmd) return null
  cmd.undo()
  redoStack.value.push(cmd)
  return cmd
}

export function redo(): Command | null {
  const cmd = redoStack.value.pop()
  if (!cmd) return null
  cmd.redo()
  undoStack.value.push(cmd)
  return cmd
}

/** New data invalidates the whole history. */
export function clearHistory(): void {
  undoStack.value.length = 0
  redoStack.value.length = 0
}

export function useUndo() {
  return { canUndo, canRedo, pushCommand, undo, redo, clearHistory }
}
