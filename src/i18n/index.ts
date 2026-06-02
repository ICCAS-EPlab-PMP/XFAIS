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
