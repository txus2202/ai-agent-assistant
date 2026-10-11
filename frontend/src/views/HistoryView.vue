<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDebateStore, type SupervisorEvent, type DebateSession } from '../stores/debate'
import { ArrowLeft, Trash2 } from '@lucide/vue'

interface DebateRecord extends DebateSession {
  id: string
  created_at: string
  events: SupervisorEvent[]
  user_request?: string
}

const router = useRouter()
const store = useDebateStore()
const debates = ref<DebateRecord[]>([])
const isLoading = ref(true)

const fetchDebates = async () => {
  try {
    const response = await fetch('/api/debates')
    if (response.ok) {
      debates.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to fetch debates:', error)
  } finally {
    isLoading.value = false
  }
}

const deleteDebate = async (id: string, event: Event) => {
  event.stopPropagation()
  if (!confirm('Are you sure you want to delete this session?')) return
  
  try {
    const response = await fetch(`/api/debates/${id}`, { method: 'DELETE' })
    if (response.ok) {
      debates.value = debates.value.filter(d => d.id !== id)
    }
  } catch (error) {
    console.error('Failed to delete debate:', error)
  }
}

onMounted(() => {
  fetchDebates()
})

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const restoreDebate = (debate: DebateRecord) => {
  store.loadDebate(debate)
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen w-full bg-space-950 text-slate-300 font-sans flex flex-col">
    <!-- Header -->
    <header class="p-6 border-b border-space-800 flex items-center justify-between bg-space-900/50">
      <div class="flex items-center space-x-4">
        <button 
          @click="router.push('/')"
          class="p-2 hover:bg-space-800 rounded-full transition-colors text-space-400 hover:text-neon-cyan"
        >
          <ArrowLeft class="w-5 h-5" />
        </button>
        <div>
          <h1 class="text-2xl font-mono font-bold tracking-widest text-white">
            SESSION HISTORY
          </h1>
          <p class="text-xs font-mono text-neon-cyan tracking-[0.2em] uppercase mt-1">
            Archived A.T.E.N.E.A Debates
          </p>
        </div>
      </div>
    </header>

    <!-- Content -->
    <main class="flex-1 p-8 overflow-y-auto custom-scrollbar">
      <div v-if="isLoading" class="flex justify-center items-center h-full">
        <div class="w-8 h-8 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></div>
      </div>
      
      <div v-else-if="debates.length === 0" class="flex flex-col items-center justify-center h-full text-space-500 font-mono">
        <p class="text-xl mb-2">No archived sessions found</p>
        <p class="text-xs">Start a new debate from the main interface</p>
      </div>

      <div v-else class="max-w-4xl mx-auto space-y-4">
        <div 
          v-for="debate in debates" 
          :key="debate.id"
          @click="restoreDebate(debate)"
          class="bg-space-900 border border-space-700 rounded-xl p-6 transition-all hover:border-neon-cyan/50 hover:bg-space-800/50 cursor-pointer group"
        >
          <div class="flex justify-between items-start">
            <div class="w-full pr-4">
              <h2 class="text-sm font-mono text-white mb-3 tracking-wide line-clamp-2 leading-relaxed italic">
                "{{ debate.user_request || (debate.events && debate.events.find(m => m.type === 'start')?.user_request) || 'No prompt recorded' }}"
              </h2>
              <p class="text-[11px] text-space-400 font-mono flex items-center space-x-4">
                <span title="Session ID" class="text-space-500 font-bold uppercase">ID: {{ debate.id.slice(0, 8) }}</span>
                <span>{{ formatDate(debate.created_at) }}</span>
                <span class="px-2 py-0.5 bg-space-800 rounded text-neon-cyan text-[10px]">
                  {{ debate.events ? debate.events.length : 0 }} events
                </span>
              </p>
            </div>
            
            <button 
              @click="deleteDebate(debate.id, $event)"
              class="p-2 text-space-600 hover:text-neon-red hover:bg-neon-red/10 rounded opacity-0 group-hover:opacity-100 transition-all shrink-0"
              title="Delete Session"
            >
              <Trash2 class="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
