import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
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
      path: '/topology',
      name: 'topology',
      component: () => import('../views/TopologyView.vue'),
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

async function handleInvalidRoute(authStore: ReturnType<typeof useAuthStore>) {
  if (authStore.user) {
    await authStore.logout()
  }
  authStore.user = null
  return { path: '/login' }
}

function handleSetupRedirect(toPath: string, isInitialized: boolean | null, isAuthenticated: boolean) {
  if (isInitialized === false) {
    return toPath !== '/setup' ? { path: '/setup' } : undefined
  }
  if (toPath === '/setup') {
    return { path: isAuthenticated ? '/' : '/login' }
  }
  return undefined
}

function handleAuthGuard(to: RouteLocationNormalized, isAuthenticated: boolean) {
  if (to.meta.requiresAuth && !isAuthenticated) {
    return {
      path: '/login',
      query: to.fullPath !== '/' ? { redirect: to.fullPath } : undefined,
    }
  }
  if (to.meta.guestOnly && isAuthenticated) {
    return { path: '/' }
  }
  return undefined
}

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (to.meta.invalidRoute) {
    return handleInvalidRoute(authStore)
  }

  if (authStore.isInitialized === null && authStore.isBackendAvailable !== false) {
    await authStore.checkAuth()
  }

  // If backend is not available, do not redirect to /setup or anywhere else
  if (authStore.isBackendAvailable === false) {
    return
  }

  const setupRedirect = handleSetupRedirect(to.path, authStore.isInitialized, authStore.isAuthenticated)
  if (setupRedirect) {
    return setupRedirect
  }

  return handleAuthGuard(to, authStore.isAuthenticated)
})

router.onError((error) => {
  console.error('Navigation error detected, logging out to login screen:', error)
  void forceLogoutToLogin()
})

export default router
