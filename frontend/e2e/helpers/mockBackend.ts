import type { Page, WebSocketRoute } from '@playwright/test'

export interface MockBackendOptions {
  initialized?: boolean
  setupTokenRequired?: boolean
  authenticated?: boolean
  isAdmin?: boolean
  username?: string
  agents?: Array<{
    id?: string
    role?: string
    name: string
    description?: string
    color_hex?: string
    state?: string
    supports_hitl?: boolean
  }>
  debates?: Array<{
    id: string
    created_at: string
    user_request?: string
    status?: string
    events?: Array<{
      type: string
      role?: string
      content?: string
      timestamp?: string
      metadata?: Record<string, unknown>
      [key: string]: unknown
    }>
  }>
}

export interface MockWsController {
  sendEvent: (event: Record<string, unknown>) => Promise<void>
  sendStreamingAssistantMessage: (text: string, role?: string) => Promise<void>
  sendHITLRequest: (prompt?: string) => Promise<void>
  sendPresentation: (markdown: string) => Promise<void>
  sendDiagram: (mermaidCode: string) => Promise<void>
  sendCode: (code: string) => Promise<void>
  waitForClientMessage: (predicate: (msg: Record<string, unknown>) => boolean, timeout?: number) => Promise<Record<string, unknown>>
}

export async function setupMockBackend(
  page: Page,
  options: MockBackendOptions = {}
): Promise<MockWsController> {
  const {
    initialized = true,
    setupTokenRequired = false,
    authenticated = true,
    isAdmin = true,
    username = 'atenea_admin',
    agents = [
      {
        id: 'supervisor',
        role: 'supervisor',
        name: 'Supervisor',
        description: 'Coordinador del consejo de agentes',
        color_hex: '#00E5FF',
        state: 'STANDBY',
        supports_hitl: true,
      },
      {
        id: 'architect',
        role: 'architect',
        name: 'Arquitecto',
        description: 'Especialista en arquitectura y diseño',
        color_hex: '#A78BFA',
        state: 'STANDBY',
      },
      {
        id: 'coder',
        role: 'coder',
        name: 'Programador',
        description: 'Implementación y refactorización de código',
        color_hex: '#34D399',
        state: 'STANDBY',
      },
    ],
    debates = [
      {
        id: 'deb-001',
        created_at: new Date().toISOString(),
        user_request: 'Diseño de arquitectura con FastAPI',
        status: 'completed',
        events: [
          {
            type: 'start',
            user_request: 'Diseño de arquitectura con FastAPI',
            timestamp: new Date().toISOString(),
          },
          {
            type: 'done',
            role: 'supervisor',
            content: 'Arquitectura establecida con Clean Architecture.',
            timestamp: new Date().toISOString(),
            metadata: { tokens: 140 },
          },
        ],
      },
      {
        id: 'deb-002',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        user_request: 'Auditoría HITL de seguridad',
        status: 'completed',
        events: [
          {
            type: 'start',
            user_request: 'Auditoría HITL de seguridad',
            timestamp: new Date(Date.now() - 3600000).toISOString(),
          },
          {
            type: 'hitl_required',
            role: 'supervisor',
            content: 'Se requiere confirmación para aplicar reglas de red.',
            timestamp: new Date(Date.now() - 3500000).toISOString(),
          },
          {
            type: 'done',
            role: 'supervisor',
            content: 'Reglas validadas y aprobadas.',
            timestamp: new Date(Date.now() - 3400000).toISOString(),
            metadata: { tokens: 280 },
          },
        ],
      },
    ],
  } = options

  let currentAuthenticated = authenticated
  let currentInitialized = initialized
  const currentUser = {
    id: 'user-001',
    username,
    is_admin: isAdmin,
    is_active: true,
    created_at: new Date().toISOString(),
  }

  let usersList = [
    currentUser,
    {
      id: 'user-002',
      username: 'dev_user',
      is_admin: false,
      is_active: true,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
  ]

  let debatesList = debates.map((d) => ({ ...d, events: d.events ?? [] }))

  // Catch-all for any other /api endpoint to prevent 401 redirects (must be registered FIRST so specific routes override it)
  await page.route('*/**/api/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    })
  })

  // Models API
  await page.route('*/**/api/models*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'gemini',
          name: 'Google Gemini',
          models: ['gemini-1.5-flash', 'gemini-1.5-pro'],
        },
      ]),
    })
  })

  // Topology API (supports GET, PUT per-user override, DELETE reset to defaults)
  const defaultTopology = {
    version: '2.0',
    project_name: 'A.T.E.N.E.A.',
    project_description: 'Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas',
    supervisor: 'Atenea',
    interpreters: ['Hermes'],
    proposers: ['Ícaro', 'Hestia'],
    reviewers: ['Sphinx'],
    evaluators: ['Sphinx'],
    implementers: ['Aracne', 'Hefesto'],
    review_rounds: 1,
    is_customized: false,
    supervisor_agent: {
      id: 'supervisor',
      name: 'Atenea',
      description: 'Orquestadora estratégica del consejo técnico.',
      color_hex: '#f59e0b',
    },
    eligible_agents: [
      { id: 'nl_interpreter', name: 'Hermes', description: 'Traduce peticiones en especificaciones técnicas.', color_hex: '#06b6d4', uses_rag: false, supports_hitl: true },
      { id: 'innovator', name: 'Ícaro', description: 'Arquitecto innovador con soluciones cloud-native.', color_hex: '#22c55e', uses_rag: true, supports_hitl: true },
      { id: 'senior_architect', name: 'Hestia', description: 'Arquitecta senior de estabilidad empresarial.', color_hex: '#00ff9d', uses_rag: true, supports_hitl: true },
      { id: 'the_judge', name: 'Sphinx', description: 'Auditora implacable de vulnerabilidades y riesgos.', color_hex: '#ef4444', uses_rag: true, supports_hitl: true },
      { id: 'devops_secops', name: 'Hefesto', description: 'DevSecOps que forja pipelines seguros y despliegues.', color_hex: '#ff8800', uses_rag: true, supports_hitl: true },
      { id: 'diagrammer', name: 'Aracne', description: 'Tejedora maestra de diagramas Mermaid.', color_hex: '#b347ff', uses_rag: true, supports_hitl: true },
      { id: 'dedalo', name: 'Dédalo', description: 'Desarrollador full-stack con Clean Code.', color_hex: '#cc7800', uses_rag: false, supports_hitl: true },
    ],
  }
  let currentTopologyState = { ...defaultTopology }

  await page.route('*/**/api/config/topology*', async (route) => {
    const method = route.request().method()
    if (method === 'PUT') {
      const body = route.request().postDataJSON() ?? {}
      currentTopologyState = {
        ...defaultTopology,
        interpreters: body.interpreters ?? [],
        proposers: body.proposers ?? [],
        reviewers: body.reviewers ?? [],
        evaluators: body.evaluators ?? [],
        implementers: body.implementers ?? [],
        review_rounds: typeof body.review_rounds === 'number' ? body.review_rounds : 1,
        is_customized: true,
      }
    } else if (method === 'DELETE') {
      currentTopologyState = { ...defaultTopology }
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(currentTopologyState),
    })
  })

  // 1. Auth Status
  await page.route('*/**/api/auth/status*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        initialized: currentInitialized,
        setup_token_required: setupTokenRequired,
        user: currentAuthenticated ? currentUser : null,
      }),
    })
  })

  // 2. Auth Login
  await page.route('*/**/api/auth/login*', async (route) => {
    const postData = route.request().postDataJSON()
    if (postData?.username === 'admin' && postData?.password === 'admin1234') {
      currentAuthenticated = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          user: currentUser,
        }),
      })
    } else {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Credenciales inválidas',
        }),
      })
    }
  })

  // 3. Auth Logout
  await page.route('*/**/api/auth/logout*', async (route) => {
    currentAuthenticated = false
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    })
  })

  // 4. Initial Setup
  await page.route('*/**/api/auth/setup*', async (route) => {
    const postData = route.request().postDataJSON()
    if (!postData?.username || !postData?.password) {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Datos incompletos para el setup' }),
      })
      return
    }

    currentInitialized = true
    currentAuthenticated = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        message: 'Administrador configurado con éxito',
        user: { ...currentUser, username: postData.username },
      }),
    })
  })

  // Observability Stats API
  await page.route('*/**/api/observability/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        cluster_status: 'HEALTHY',
        cpu_percent: 38.0,
        memory_percent: 62.0,
        active_agents_count: 0,
        additional_stats: {},
        langfuse_metrics_enabled: false,
        langfuse_dashboard_url: 'http://localhost:3000',
      }),
    })
  })

  // 5. Users API (/api/auth/users)
  await page.route(/\/api\/auth\/users(?:\/|\?|$)/, async (route) => {
    const method = route.request().method()
    const url = route.request().url()

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(usersList),
      })
    } else if (method === 'POST') {
      const postData = route.request().postDataJSON()
      const newUser = {
        id: `user-${Date.now()}`,
        username: postData.username || 'nuevo_usuario',
        is_admin: !!postData.is_admin,
        is_active: true,
        created_at: new Date().toISOString(),
      }
      usersList.push(newUser)
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(newUser),
      })
    } else if (method === 'DELETE') {
      const userId = url.split('/').pop()?.split('?')[0]
      usersList = usersList.filter((u) => u.id !== userId)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Usuario eliminado' }),
      })
    } else {
      await route.fallback()
    }
  })

  // 6. Agents Config
  await page.route('*/**/api/config/agents*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(agents),
    })
  })

  // 7. Debates History
  await page.route(/\/api\/debates(?:\/|\?|$)/, async (route) => {
    const method = route.request().method()
    const parsedUrl = new URL(route.request().url())
    const pathParts = parsedUrl.pathname.split('/').filter(Boolean)
    const debatesSegmentIdx = pathParts.lastIndexOf('debates')
    const maybeDebateId =
      debatesSegmentIdx >= 0 && pathParts.length > debatesSegmentIdx + 1
        ? pathParts[debatesSegmentIdx + 1]
        : undefined

    if (method === 'GET' && maybeDebateId) {
      const found = debatesList.find((d) => d.id === maybeDebateId)
      if (!found) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Debate not found' }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(found),
      })
    } else if (method === 'GET') {
      const limit = Math.max(1, Number.parseInt(parsedUrl.searchParams.get('limit') || '20', 10) || 20)
      const offset = Math.max(0, Number.parseInt(parsedUrl.searchParams.get('offset') || '0', 10) || 0)
      const filter = parsedUrl.searchParams.get('filter') || 'all'
      const search = (parsedUrl.searchParams.get('search') || '').trim().toLowerCase()

      const filtered = debatesList.filter((d) => {
        if (filter === 'hitl') {
          const hitl = d.events.some((e) => String(e.type || '').toLowerCase().includes('hitl'))
          if (!hitl) return false
        }
        if (search) {
          const haystack = `${d.id} ${d.user_request} ${JSON.stringify(d.events)}`.toLowerCase()
          if (!haystack.includes(search)) return false
        }
        return true
      })

      const pageItems = filtered.slice(offset, offset + limit).map((d) => {
        const hasHitl = d.events.some((e) => String(e.type || '').toLowerCase().includes('hitl'))
        const agents = Array.from(
          new Set(
            d.events
              .map((e) => e.role)
              .filter((r): r is string => typeof r === 'string' && r.length > 0 && r !== 'supervisor')
          )
        )
        const totalTokens = d.events.reduce((acc, e) => {
          const meta = e.metadata as Record<string, unknown> | undefined
          const raw = meta?.total_tokens ?? meta?.tokens
          return acc + (typeof raw === 'number' || typeof raw === 'string' ? Number(raw) || 0 : 0)
        }, 0)
        const lastConclusion = [...d.events]
          .reverse()
          .find((e) => typeof e.content === 'string' && e.content.trim().length > 0)?.content
        return {
          id: d.id,
          created_at: d.created_at,
          user_request: d.user_request,
          target_agent: 'supervisor',
          status: d.status,
          event_count: d.events.length,
          total_tokens: totalTokens,
          has_hitl: hasHitl,
          conclusion: typeof lastConclusion === 'string' ? `${lastConclusion.slice(0, 160)}...` : '',
          agents,
        }
      })

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: filtered.length,
          total_all: debatesList.length,
          limit,
          offset,
          items: pageItems,
        }),
      })
    } else if (method === 'DELETE') {
      const debateId = maybeDebateId ?? parsedUrl.pathname.split('/').pop()
      debatesList = debatesList.filter((d) => d.id !== debateId)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Debate eliminado' }),
      })
    } else {
      await route.fallback()
    }
  })

  // 8. WebSocket Route
  let activeWs: WebSocketRoute | null = null
  let resolveWsReady: (() => void) | null = null
  const wsReadyPromise = new Promise<void>((resolve) => {
    resolveWsReady = resolve
  })
  const clientMessages: Array<Record<string, unknown>> = []

  await page.routeWebSocket('**/ws/debate', (ws) => {
    activeWs = ws
    if (resolveWsReady) {
      resolveWsReady()
      resolveWsReady = null
    }

    ws.onMessage((message) => {
      try {
        const parsed = JSON.parse(message.toString())
        clientMessages.push(parsed)
      } catch {
        // ignore non-json
      }
    })
  })

  // Mock wake-word websocket
  await page.routeWebSocket('**/ws/audio/wake-word', (ws) => {
    ws.onMessage(() => {})
  })

  const getActiveWs = async (): Promise<WebSocketRoute> => {
    if (activeWs) return activeWs
    await wsReadyPromise
    return activeWs!
  }

  const controller: MockWsController = {
    sendEvent: async (event: Record<string, unknown>) => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          timestamp: new Date().toISOString(),
          ...event,
        })
      )
    },

    sendStreamingAssistantMessage: async (text: string, role = 'supervisor') => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          type: 'message',
          role,
          content: text,
          timestamp: new Date().toISOString(),
        })
      )
      await page.waitForTimeout(50)
    },

    sendHITLRequest: async (prompt = '¿Deseas autorizar la ejecución del despliegue?') => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          type: 'hitl_required',
          role: 'supervisor',
          content: prompt,
          options: ['approve', 'refine', 'divert', 'retry'],
          timestamp: new Date().toISOString(),
        })
      )
    },

    sendPresentation: async (markdown: string) => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          type: 'message',
          role: 'supervisor',
          content: '```presentation\n' + markdown + '\n```',
          timestamp: new Date().toISOString(),
        })
      )
    },

    sendDiagram: async (mermaidCode: string) => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          type: 'message',
          role: 'supervisor',
          content: '```mermaid\n' + mermaidCode + '\n```',
          timestamp: new Date().toISOString(),
        })
      )
    },

    sendCode: async (code: string) => {
      const ws = await getActiveWs()
      ws.send(
        JSON.stringify({
          type: 'message',
          role: 'supervisor',
          content: '```typescript\n' + code + '\n```',
          timestamp: new Date().toISOString(),
        })
      )
    },

    waitForClientMessage: async (predicate, timeout = 5000) => {
      const startTime = Date.now()
      while (Date.now() - startTime < timeout) {
        const found = clientMessages.find(predicate)
        if (found) return found
        await page.waitForTimeout(50)
      }
      throw new Error(`Timeout waiting for client WS message matching predicate`)
    },
  }

  return controller
}

