<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDebateStore, type SupervisorEvent, type DebateSession } from '../stores/debate'
import { historyService, type PaginatedDebatesResponse } from '../services/historyService'
import { ArrowLeft, Trash2, Search, ArrowRight, Clock } from '@lucide/vue'

interface DebateSummaryItem extends DebateSession {
  id: string
  created_at: string
  user_request?: string
  target_agent?: string
  status?: string
  event_count?: number
  total_tokens?: number
  has_hitl?: boolean
  conclusion?: string
  agents?: string[]
  events?: SupervisorEvent[]
}

const router = useRouter()
const store = useDebateStore()
const debates = ref<DebateSummaryItem[]>([])
const isLoading = ref(true)
const isLoadingMore = ref(false)
const loadingDetailId = ref<string | null>(null)

const searchQuery = ref('')
const activeFilter = ref<'all' | 'hitl' | 'today' | 'week'>('all')
const pageSize = 20
const clientDisplayedCount = ref(pageSize)
const totalCount = ref(0)
const totalAllCount = ref(0)
const nextOffset = ref(0)
const isServerPaginated = ref(true)

let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null
let activeFetchSeq = 0

const fetchDebates = async (reset = true) => {
  const requestSeq = ++activeFetchSeq
  const targetOffset = reset ? 0 : nextOffset.value
  if (reset) {
    isLoading.value = debates.value.length === 0
  } else {
    isLoadingMore.value = true
  }

  try {
    const payload: unknown = await historyService.listDebates({
      limit: pageSize,
      offset: targetOffset,
      filter: activeFilter.value,
      search: searchQuery.value,
    })
    if (requestSeq !== activeFetchSeq) return

    if (Array.isArray(payload)) {
      isServerPaginated.value = false
      const items = payload as DebateSummaryItem[]
      debates.value = items
      totalCount.value = items.length
      totalAllCount.value = items.length
      nextOffset.value = items.length
      return
    }

    if (payload && typeof payload === 'object') {
      const page = payload as PaginatedDebatesResponse
      const incoming = (Array.isArray(page.items) ? page.items : []) as DebateSummaryItem[]
      isServerPaginated.value = true
      if (reset) {
        debates.value = incoming
        nextOffset.value = incoming.length
      } else {
        const existingIds = new Set(debates.value.map(d => d.id))
        const uniqueIncoming = incoming.filter(item => !existingIds.has(item.id))
        debates.value = [...debates.value, ...uniqueIncoming]
        nextOffset.value = targetOffset + incoming.length
      }
      totalCount.value = typeof page.total === 'number' ? page.total : debates.value.length
      totalAllCount.value = typeof page.total_all === 'number' ? page.total_all : totalCount.value
    }
  } catch (error) {
    console.error('Failed to fetch debates:', error)
  } finally {
    if (requestSeq === activeFetchSeq) {
      isLoading.value = false
      isLoadingMore.value = false
    }
  }
}

const deleteDebate = async (id: string, event: Event) => {
  event.stopPropagation()
  if (!confirm('Are you sure you want to delete this session?')) return

  try {
    await historyService.deleteDebate(id)
    debates.value = debates.value.filter(d => d.id !== id)
    totalCount.value = Math.max(0, totalCount.value - 1)
    totalAllCount.value = Math.max(0, totalAllCount.value - 1)
    nextOffset.value = Math.max(0, nextOffset.value - 1)
  } catch (error) {
    console.error('Failed to delete debate:', error)
  }
}

onMounted(async () => {
  await fetchDebates(true)
})

onUnmounted(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
})

const getDebatePrompt = (debate: DebateSummaryItem): string => {
  if (debate.user_request) return debate.user_request
  const startEvt = debate.events?.find(m => m.type === 'start')
  if (startEvt?.user_request && typeof startEvt.user_request === 'string') return startEvt.user_request
  return 'No prompt recorded'
}

const getDebateEventCount = (debate: DebateSummaryItem): number => {
  if (typeof debate.event_count === 'number') return debate.event_count
  return Array.isArray(debate.events) ? debate.events.length : 0
}

const getDebateTokens = (debate: DebateSummaryItem): number => {
  if (typeof debate.total_tokens === 'number') return debate.total_tokens
  if (!debate.events || !Array.isArray(debate.events)) return 0
  const metricEventTypes = new Set(['done', 'agent_completed', 'synthesis', 'conclusion', 'final_response'])
  let total = 0
  for (let idx = 0; idx < debate.events.length; idx++) {
    const ev = debate.events[idx]
    if (!ev || !ev.type || !metricEventTypes.has(ev.type)) continue
    if (ev.type === 'done') {
      if (ev.metadata?.metrics_reported === 'true') continue
      const prev = idx > 0 ? debate.events[idx - 1] : undefined
      const evTokens = ev.metadata?.total_tokens ?? ev.metadata?.tokens
      const prevTokens = prev?.metadata?.total_tokens ?? prev?.metadata?.tokens
      if (
        prev?.type === 'agent_completed' &&
        prev.role === ev.role &&
        evTokens !== undefined &&
        evTokens === prevTokens
      ) {
        continue
      }
    }

    const rawTokens = ev.metadata?.total_tokens ?? ev.metadata?.tokens
    if (rawTokens) {
      total += Number.parseInt(String(rawTokens), 10) || 0
    } else if (ev.content && typeof ev.content === 'string') {
      const words = ev.content.trim().split(/\s+/).filter(Boolean).length
      total += Math.max(12, Math.round(words * 1.35))
    }
  }
  return total
}

const getDebateAgents = (debate: DebateSummaryItem): string[] => {
  if (Array.isArray(debate.agents)) return debate.agents
  if (!debate.events || !Array.isArray(debate.events)) return []
  const set = new Set<string>()
  for (const ev of debate.events) {
    if (ev.role && ev.role !== 'supervisor' && typeof ev.role === 'string') {
      set.add(ev.role)
    }
  }
  return Array.from(set)
}

const hasHitl = (debate: DebateSummaryItem): boolean => {
  if (typeof debate.has_hitl === 'boolean') return debate.has_hitl
  if (!debate.events || !Array.isArray(debate.events)) return false
  return debate.events.some(e =>
    e.type === 'hitl_required' ||
    e.type === 'hitl_approval_required' ||
    e.type === 'hitl_feedback' ||
    e.type?.includes('hitl')
  )
}

const getDebateConclusion = (debate: DebateSummaryItem): string => {
  if (typeof debate.conclusion === 'string') return debate.conclusion
  if (!debate.events || !Array.isArray(debate.events)) return ''
  const rev = [...debate.events].reverse()
  const conclusionEvt = rev.find(e =>
    e.content &&
    (
      e.type === 'done' ||
      e.type === 'agent_completed' ||
      e.type === 'message' ||
      e.type === 'synthesis' ||
      e.type === 'conclusion' ||
      e.type === 'final_response'
    )
  )
  if (conclusionEvt?.content && typeof conclusionEvt.content === 'string') {
    return conclusionEvt.content.trim().replace(/^#+\s*/g, '').slice(0, 160) + '...'
  }
  return ''
}

const totalTokensAll = computed(() => {
  return debates.value.reduce((sum, d) => sum + getDebateTokens(d), 0)
})

const totalHitlCount = computed(() => {
  return debates.value.filter(d => hasHitl(d)).length
})

const filteredDebates = computed(() => {
  if (isServerPaginated.value) {
    return debates.value
  }
  const query = searchQuery.value.trim().toLowerCase()
  const now = new Date()
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

  return debates.value.filter(d => {
    if (activeFilter.value === 'hitl' && !hasHitl(d)) return false
    if (activeFilter.value === 'today') {
      const dDate = new Date(d.created_at)
      if (dDate < oneDayAgo) return false
    }
    if (activeFilter.value === 'week') {
      const dDate = new Date(d.created_at)
      if (dDate < oneWeekAgo) return false
    }

    if (!query) return true
    const prompt = getDebatePrompt(d).toLowerCase()
    const id = d.id.toLowerCase()
    const conclusion = getDebateConclusion(d).toLowerCase()
    const agents = getDebateAgents(d).join(' ').toLowerCase()
    return prompt.includes(query) || id.includes(query) || conclusion.includes(query) || agents.includes(query)
  })
})

const paginatedDebates = computed(() => {
  if (isServerPaginated.value) {
    return debates.value
  }
  return filteredDebates.value.slice(0, clientDisplayedCount.value)
})

const effectiveTotalCount = computed(() => {
  return isServerPaginated.value ? totalCount.value : filteredDebates.value.length
})

const hasMoreDebates = computed(() => {
  return paginatedDebates.value.length < effectiveTotalCount.value
})

watch(activeFilter, () => {
  clientDisplayedCount.value = pageSize
  if (isServerPaginated.value) {
    void fetchDebates(true)
  }
})

watch(searchQuery, () => {
  clientDisplayedCount.value = pageSize
  if (isServerPaginated.value) {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
    }
    searchDebounceTimer = setTimeout(() => {
      searchDebounceTimer = null
      void fetchDebates(true)
    }, 150)
  }
})

const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement
  if (!target) return
  if (target.scrollHeight - target.scrollTop - target.clientHeight < 250) {
    if (isServerPaginated.value) {
      if (!isLoadingMore.value && debates.value.length < totalCount.value) {
        void fetchDebates(false)
      }
    } else if (clientDisplayedCount.value < filteredDebates.value.length) {
      clientDisplayedCount.value += pageSize
    }
  }
}

const formatDate = (dateString: string) => {
  try {
    return new Date(dateString).toLocaleString()
  } catch {
    return dateString
  }
}

const formatRelativeTime = (dateString: string) => {
  try {
    const d = new Date(dateString)
    const now = new Date()
    const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60)
    if (diffHours < 2) return 'Hace un momento'
    if (diffHours < 24) return `Hoy, ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    if (diffHours < 48) return `Ayer, ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    return d.toLocaleDateString([], { day: '2-digit', month: 'short' })
  } catch {
    return dateString
  }
}

const restoreDebate = async (debate: DebateSummaryItem) => {
  if (loadingDetailId.value === debate.id) return

  const needsDetailFetch =
    !Array.isArray(debate.events) ||
    (typeof debate.event_count === 'number' && debate.events.length < debate.event_count)

  let fullSession: DebateSession = debate
  if (needsDetailFetch) {
    loadingDetailId.value = debate.id
    try {
      const detail: unknown = await historyService.getDebate(debate.id)
      if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        fullSession = detail as DebateSession
      }
    } catch (error) {
      console.error('Failed to load debate details:', error)
      return
    } finally {
      loadingDetailId.value = null
    }
  }

  store.loadDebate(fullSession)
  await router.push('/')
}
</script>

<template>
  <div class="h-screen max-h-screen w-full bg-space-950 text-slate-300 font-sans flex flex-col overflow-hidden">
    <!-- Header -->
    <header class="p-4 sm:p-5 border-b border-space-800/80 bg-space-900/90 backdrop-blur-md shrink-0 z-20">
      <div class="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <!-- Back and Title -->
        <div class="flex items-center space-x-3 sm:space-x-4">
          <button 
            @click="router.push('/')"
            data-test="history-back-btn"
            class="p-2 sm:p-2.5 bg-space-850 hover:bg-space-800 border border-space-700/60 hover:border-cyan-500/40 rounded-xl transition-all text-slate-400 hover:text-cyan-300 shadow-sm shrink-0 cursor-pointer"
            title="Volver al chat"
          >
            <ArrowLeft class="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
          <div>
            <h1 class="text-lg sm:text-xl font-mono font-bold tracking-wider text-white flex items-center gap-2">
              HISTORIAL DE CONVERSACIONES
            </h1>
            <p class="text-[11px] font-mono text-cyan-400 tracking-[0.15em] uppercase mt-0.5">
              DEBATES ARCHIVADOS
            </p>
          </div>
        </div>

        <!-- Global Stats KPIs -->
        <div class="flex items-center gap-2 sm:gap-3 text-xs font-mono">
          <div class="bg-space-850/80 border border-space-700/60 rounded-lg px-3 py-1.5 flex items-center gap-2">
            <span class="text-slate-400">Sesiones:</span>
            <span class="text-white font-bold">{{ totalAllCount }}</span>
          </div>
          <div class="bg-space-850/80 border border-space-700/60 rounded-lg px-3 py-1.5 flex items-center gap-2">
            <span class="text-slate-400">Tokens:</span>
            <span class="text-cyan-300 font-bold">🪙 {{ totalTokensAll.toLocaleString() }}</span>
          </div>
          <div v-if="totalHitlCount > 0" class="bg-space-850/80 border border-space-700/60 rounded-lg px-3 py-1.5 hidden md:flex items-center gap-2">
            <span class="text-slate-400">HITL:</span>
            <span class="text-amber-400 font-bold">{{ totalHitlCount }}</span>
          </div>
        </div>
      </div>
    </header>

    <!-- Fixed Search & Filter Controls Bar -->
    <div class="shrink-0 p-3 sm:p-4 border-b border-space-800/80 bg-space-900/40">
      <div class="max-w-6xl mx-auto flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        <!-- Search Bar -->
        <div class="relative flex-1 min-w-0">
          <label for="history-search-input" class="sr-only">Buscar por objetivo, agente o ID de sesión</label>
          <Search class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" aria-hidden="true" />
          <input 
            id="history-search-input"
            v-model="searchQuery" 
            type="text" 
            name="searchQuery"
            data-test="history-search-input"
            placeholder="Buscar por objetivo, agente o ID de sesión..." 
            class="w-full bg-space-850/90 border border-space-700/80 focus:border-cyan-500/50 rounded-lg pl-10 pr-4 py-2 text-xs font-mono text-slate-200 placeholder-slate-500 outline-none transition-colors"
          />
        </div>

        <!-- Filter Pills -->
        <div class="flex items-center gap-1.5 shrink-0 overflow-x-auto pb-1 md:pb-0">
          <button 
            type="button"
            @click="activeFilter = 'all'"
            class="px-3 py-1.5 rounded-lg text-xs font-mono border transition-all cursor-pointer whitespace-nowrap"
            :class="activeFilter === 'all' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold' : 'bg-space-850/60 text-slate-400 border-space-700 hover:border-slate-600'"
          >
            Todas ({{ totalAllCount }})
          </button>
          <button 
            type="button"
            @click="activeFilter = 'hitl'"
            class="px-3 py-1.5 rounded-lg text-xs font-mono border transition-all cursor-pointer whitespace-nowrap"
            :class="activeFilter === 'hitl' ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 font-bold' : 'bg-space-850/60 text-slate-400 border-space-700 hover:border-slate-600'"
          >
            Con HITL
          </button>
          <button 
            type="button"
            @click="activeFilter = 'today'"
            class="px-3 py-1.5 rounded-lg text-xs font-mono border transition-all cursor-pointer whitespace-nowrap"
            :class="activeFilter === 'today' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold' : 'bg-space-850/60 text-slate-400 border-space-700 hover:border-slate-600'"
          >
            Hoy
          </button>
          <button 
            type="button"
            @click="activeFilter = 'week'"
            class="px-3 py-1.5 rounded-lg text-xs font-mono border transition-all cursor-pointer whitespace-nowrap"
            :class="activeFilter === 'week' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold' : 'bg-space-850/60 text-slate-400 border-space-700 hover:border-slate-600'"
          >
            Esta semana
          </button>
        </div>
      </div>
    </div>

    <!-- Scrollable Cards Main Container -->
    <main @scroll="handleScroll" class="flex-1 overflow-y-auto custom-scrollbar p-4 sm:p-6 lg:p-8 min-h-0">
      <div class="max-w-6xl mx-auto space-y-5">

        <!-- Loading State -->
        <div v-if="isLoading" class="flex flex-col justify-center items-center py-20 text-slate-500 font-mono gap-3">
          <div class="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
          <span class="text-xs">Cargando archivo de deliberaciones...</span>
        </div>
        
        <!-- Empty State (No debates stored) -->
        <div v-else-if="totalAllCount === 0 && debates.length === 0 && !searchQuery.trim() && activeFilter === 'all'" class="flex flex-col items-center justify-center py-20 text-space-500 font-mono">
          <p class="text-xl mb-2 text-slate-400 font-semibold">No archived sessions found</p>
          <p class="text-xs text-slate-500">Start a new debate from the main interface</p>
        </div>

        <!-- No Filter Results -->
        <div v-else-if="filteredDebates.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-500 font-mono">
          <p class="text-base text-slate-400 mb-1">No se encontraron sesiones que coincidan</p>
          <p class="text-xs">Prueba a limpiar la búsqueda o cambiar el filtro</p>
        </div>

        <!-- Sessions Grid (Responsive: 1 col on mobile, 2 col on tablet/desktop) -->
        <div v-else class="space-y-4">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div 
              v-for="debate in paginatedDebates" 
              :key="debate.id"
              class="group relative bg-space-900/80 hover:bg-space-850/90 border border-space-700/80 hover:border-cyan-500/50 rounded-xl p-4 sm:p-5 transition-all duration-200 flex flex-col justify-between shadow-sm hover:shadow-cyan-500/5"
            >
              <!-- Card Header: ID, date, tag & delete button -->
              <div class="flex items-center justify-between gap-2 pb-2.5 border-b border-space-800">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-space-800 text-slate-400 border border-space-700/80 uppercase">
                    ID: {{ debate.id.slice(0, 8) }}
                  </span>
                  <span class="text-[11px] font-mono text-slate-400 flex items-center gap-1 truncate" :title="formatDate(debate.created_at)">
                    <Clock class="w-3 h-3 text-slate-500 shrink-0" />
                    <span>{{ formatRelativeTime(debate.created_at) }}</span>
                  </span>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                  <span 
                    v-if="hasHitl(debate)"
                    class="text-[9px] font-mono px-2 py-0.5 rounded border bg-amber-500/10 text-amber-400 border-amber-500/30 font-semibold"
                  >
                    HITL
                  </span>
                  <button 
                    type="button"
                    @click="deleteDebate(debate.id, $event)"
                    data-test="delete-session-btn"
                    class="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                    title="Delete Session"
                    aria-label="Delete Session"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </div>

              <!-- Card Body Button (Restores session on click) -->
              <button 
                type="button"
                @click="restoreDebate(debate)"
                data-test="session-card"
                class="session-card w-full text-left pt-3 flex flex-col flex-1 focus:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500/50 rounded-lg cursor-pointer"
              >
                <!-- User prompt -->
                <h2 class="text-sm font-mono text-white mb-2 tracking-wide line-clamp-2 leading-relaxed italic group-hover:text-cyan-200 transition-colors">
                  "{{ getDebatePrompt(debate) }}"
                </h2>

                <!-- Conclusion snippet if available -->
                <p v-if="getDebateConclusion(debate)" class="text-xs text-slate-400 font-sans line-clamp-2 leading-relaxed mb-3 bg-space-850/50 border border-space-800/80 rounded-lg p-2.5">
                  <span class="text-[10px] font-mono text-cyan-400/80 uppercase font-semibold block mb-0.5">Conclusión:</span>
                  {{ getDebateConclusion(debate) }}
                </p>

                <!-- Participating agent badges -->
                <div v-if="getDebateAgents(debate).length > 0" class="flex flex-wrap gap-1 mb-3">
                  <span 
                    v-for="ag in getDebateAgents(debate)" 
                    :key="ag"
                    class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-space-800/80 border border-space-700/60 text-slate-300 uppercase"
                  >
                    {{ ag.replaceAll('_', ' ') }}
                  </span>
                </div>

                <!-- Footer row: events, tokens and resume action -->
                <div class="mt-auto pt-2.5 border-t border-space-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <div class="flex items-center gap-3">
                    <span class="px-2 py-0.5 bg-space-800 rounded text-cyan-300 text-[10px]">
                      {{ getDebateEventCount(debate) }} events
                    </span>
                    <span class="flex items-center gap-1 text-slate-300 text-[10px]">
                      🪙 {{ getDebateTokens(debate).toLocaleString() }}
                    </span>
                  </div>

                  <span class="text-cyan-400 flex items-center gap-1 text-xs font-semibold group-hover:translate-x-0.5 transition-transform">
                    Reanudar debate
                    <ArrowRight class="w-3.5 h-3.5" />
                  </span>
                </div>
              </button>
            </div>
          </div>

          <!-- Pagination Indicator / Footer -->
          <div v-if="isLoadingMore" class="text-center py-3 text-xs font-mono text-cyan-400">
            Cargando más sesiones...
          </div>
          <div v-else-if="hasMoreDebates" class="text-center py-4 text-xs font-mono text-slate-500">
            Mostrando {{ paginatedDebates.length }} de {{ effectiveTotalCount }} sesiones (haz scroll para cargar más)
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
