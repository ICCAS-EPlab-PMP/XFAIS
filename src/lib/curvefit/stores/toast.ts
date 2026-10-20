/**
 * Toast store: bottom-right notifications.
 */
import { ref } from 'vue'

export type ToastKind = 'info' | 'success' | 'warn' | 'error'

export interface ToastItem {
  id: number
  kind: ToastKind
  msg: string
}

const items = ref<ToastItem[]>([])
let seq = 0

export function pushToast(kind: ToastKind, msg: string, ttl = 3800): void {
  const id = ++seq
  items.value.push({ id, kind, msg })
  if (items.value.length > 5) items.value.splice(0, items.value.length - 5)
  window.setTimeout(() => dismissToast(id), ttl)
}

export function dismissToast(id: number): void {
  const i = items.value.findIndex((t) => t.id === id)
  if (i >= 0) items.value.splice(i, 1)
}

export function useToasts() {
  return { items, pushToast, dismissToast }
}
