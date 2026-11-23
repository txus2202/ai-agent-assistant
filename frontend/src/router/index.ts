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
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found-fallback',
      component: () => import('../views/LoginView.vue'),
      meta: { invalidRoute: true },
    },
  ],
})

export async function forceLogoutToLogin(redirectPath?: string): Promise<void> {
  const authStore = useAuthStore()
  if (authStore.user) {
    await authStore.logout()
  }
  authStore.user = null
  if (router.currentRoute.value.path !== '/login') {
    await router.push({
      path: '/login',
      query: redirectPath && redirectPath !== '/' && redirectPath !== '/login' ? { redirect: redirectPath } : undefined,
    })
  }
}

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (to.meta.invalidRoute) {
    if (authStore.user) {
      await authStore.logout()
    }
    authStore.user = null
    return { path: '/login' }
  }

  if (authStore.isInitialized === null && authStore.isBackendAvailable !== false) {
    await authStore.checkAuth()
  }

  // If backend is not available, do not redirect to /setup or anywhere else
  if (authStore.isBackendAvailable === false) {
    return
  }

  // System not yet configured with an initial admin (backend is reachable and 0 users exist)
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

router.onError((error) => {
  console.error('Navigation error detected, logging out to login screen:', error)
  void forceLogoutToLogin()
})

export default router
