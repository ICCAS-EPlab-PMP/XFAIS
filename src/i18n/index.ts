import { createI18n } from 'vue-i18n'
import { localeStorageKey, messages, type AppLocale } from './messages'

const savedLocale = localStorage.getItem(localeStorageKey)
const locale = (savedLocale === 'zh' || savedLocale === 'en' ? savedLocale : 'zh') as AppLocale

const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'en',
  messages
})

export default i18n

/** Global translate usable outside components (lib helpers, drop-zone toasts). */
export const globalT = (key: string, named?: Record<string, unknown>): string =>
  i18n.global.t(key, named ?? {})
