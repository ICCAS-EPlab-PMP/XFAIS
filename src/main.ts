import { createApp } from 'vue'
import App from './App.vue'
import i18n from './i18n'
import router from './router'
import { toastKey, toastStore } from './lib/toast'
import { TransportPlugin } from './lib/transport-plugin'
import './styles/global.css'

const app = createApp(App)

app.use(router)
app.use(i18n)
app.use(TransportPlugin)
app.provide(toastKey, toastStore)
app.config.globalProperties.$toast = toastStore.push

router.onError((error) => {
  toastStore.push({
    title: 'Routing error',
    message: error instanceof Error ? error.message : 'Unknown routing error',
    tone: 'error'
  })
})

app.mount('#app')
