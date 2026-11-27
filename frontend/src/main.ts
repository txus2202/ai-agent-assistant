import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { registerAteneaServiceWorker } from './pwa/registerServiceWorker'
import router, { forceLogoutToLogin } from './router'
import { httpClient } from './services/httpClient'
import { useAuthStore } from './stores/auth'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)

app.config.errorHandler = (err) => {
  console.error('Global Vue error handled, logging out to login screen:', err)
  void forceLogoutToLogin()
}

httpClient.configure({
  onUnauthorized: () => {
    const authStore = useAuthStore()
    authStore.user = null
    if (router.currentRoute.value.path !== '/login') {
      void router.push({
        path: '/login',
        query:
          router.currentRoute.value.fullPath !== '/'
            ? { redirect: router.currentRoute.value.fullPath }
            : undefined,
      })
    }
  },
})

app.mount('#app')

if (typeof window !== 'undefined') {
  window.addEventListener(
    'load',
    () => {
      void registerAteneaServiceWorker()
    },
    { once: true },
  )
}
