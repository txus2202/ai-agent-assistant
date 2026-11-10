import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)

// Global 401 response interceptor
const originalFetch = window.fetch
window.fetch = async (...args) => {
  const response = await originalFetch(...args)
  if (response.status === 401) {
    const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url
    if (
      !url.includes('/api/auth/login') &&
      !url.includes('/api/auth/status') &&
      !url.includes('/api/auth/change-password')
    ) {
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
    }
  }
  return response
}

app.mount('#app')
