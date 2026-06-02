import { inject, type InjectionKey, reactive } from 'vue'

export type ToastTone = 'info' | 'success' | 'error'

export interface ToastItem {
  id: number
  title: string
  message: string
  tone: ToastTone
}

export interface ToastInput {
  title: string
  message: string
  tone?: ToastTone
}

interface ToastStore {
  items: ToastItem[]
  push: (input: ToastInput) => void
  remove: (id: number) => void
}

let seed = 0

export const toastStore = reactive<ToastStore>({
  items: [],
  push(input) {
    const id = ++seed
    toastStore.items.push({
      id,
      title: input.title,
      message: input.message,
      tone: input.tone ?? 'info'
    })

    window.setTimeout(() => {
      toastStore.remove(id)
    }, 4000)
  },
  remove(id) {
    const index = toastStore.items.findIndex((item) => item.id === id)
    if (index >= 0) {
      toastStore.items.splice(index, 1)
    }
  }
})

export const toastKey: InjectionKey<ToastStore> = Symbol('toast-store')

export const useToast = (): ToastStore => {
  const store = inject(toastKey)
  if (!store) {
    throw new Error('Toast store is not available')
  }

  return store
}
