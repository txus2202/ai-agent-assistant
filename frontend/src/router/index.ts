import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/HistoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('../views/InitialSetupView.vue'),
      meta: { setupOnly: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (authStore.isInitialized === null) {
    await authStore.checkAuth()
  }

  // System not yet configured with an initial admin
  if (authStore.isInitialized === false) {
    if (to.path !== '/setup') {
      return { path: '/setup' }
    }
    return
  }

  // System is initialized
  if (to.path === '/setup') {
    return { path: authStore.isAuthenticated ? '/' : '/login' }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return {
      path: '/login',
      query: to.fullPath !== '/' ? { redirect: to.fullPath } : undefined,
    }
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return { path: '/' }
  }
})

export default router
