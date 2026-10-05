<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { SendHorizontal, Paperclip, Activity, MessageSquare, Check, User, Bot, ChevronDown } from 'lucide-vue-next'
import { useDebateStore } from '../stores/debate'

const props = defineProps<{
  messages: Array<{ role: 'user' | 'assistant', content: string }>
  isDebating: boolean
}>()

const store = useDebateStore()

const inputMsg = ref('')
const selectedAgent = ref('supervisor')
const selectedFile = ref<File | null>(null)
const chatScroll = ref<HTMLElement | null>(null)

// Custom Agent Dropdown Logic
const isAgentDropdownOpen = ref(false)
const agentDropdownRef = ref<HTMLElement | null>(null)

const agentsList = [
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'nl_interpreter', label: 'NL Interpreter' },
  { value: 'innovator_architect', label: 'Innovator Architect' },
  { value: 'senior_architect', label: 'Senior Architect' },
  { value: 'the_judge', label: 'The Judge' },
  { value: 'diagrammer', label: 'Diagrammer' },
  { value: 'devops_secops', label: 'DevOps & SecOps' },
  { value: 'learning', label: 'Learning Agent' }
]

const selectedAgentLabel = computed(() => {
  return agentsList.find(a => a.value === selectedAgent.value)?.label || 'Supervisor'
})

const toggleAgentDropdown = () => {
  if (props.isDebating) return
  isAgentDropdownOpen.value = !isAgentDropdownOpen.value
}

const selectAgent = (value: string) => {
  selectedAgent.value = value
  isAgentDropdownOpen.value = false
}

const handleClickOutsideAgent = (event: MouseEvent) => {
  if (!agentDropdownRef.value || !isAgentDropdownOpen.value) return
  const path = event.composedPath()
  if (!path.includes(agentDropdownRef.value)) {
    isAgentDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutsideAgent)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideAgent)
})

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0]
  }
}

const onSubmit = async () => {
  if (!inputMsg.value.trim() || props.isDebating) return
  
  let attachmentUrl = null
  if (selectedFile.value) {
    try {
      attachmentUrl = await store.uploadFile(selectedFile.value)
    } catch (e) {
      console.error('Failed to upload file:', e)
      alert('Error uploading file. Please try again.')
      return
    }
  }

  store.startDebate(inputMsg.value, selectedAgent.value, attachmentUrl)
  
  inputMsg.value = ''
  selectedFile.value = null
}

const clearChat = () => {
  if (confirm('¿Seguro que deseas limpiar la conversación actual?')) {
    store.messages.splice(0, store.messages.length)
    store.rawEvents.splice(0, store.rawEvents.length)
  }
}

// Auto-scroll to bottom when messages change
watch(() => props.messages.length, async () => {
  await nextTick()
  if (chatScroll.value) {
    chatScroll.value.scrollTop = chatScroll.value.scrollHeight
  }
})
</script>

<template>
  <div class="flex flex-col h-full bg-[#060a11] border-r border-space-800 font-sans">
    
    <!-- Top Tabs -->
    <div class="flex items-center justify-between p-4 border-b border-space-800">
      <div class="flex space-x-6">
        <button class="flex items-center space-x-2 text-space-500 font-mono text-[10px] tracking-widest uppercase hover:text-slate-400 transition-colors">
          <Activity class="w-3.5 h-3.5" />
          <span>Observabilidad</span>
        </button>
        <button class="flex items-center space-x-2 text-neon-cyan font-mono text-[10px] tracking-widest uppercase border border-neon-cyan/30 bg-[#002b36] px-3 py-1.5 rounded">
          <MessageSquare class="w-3.5 h-3.5" />
          <span>Chat con IA</span>
          <span class="bg-neon-cyan/20 text-neon-cyan px-1.5 py-0.5 rounded-sm text-[8px] ml-2">ACTIVO</span>
        </button>
      </div>
    </div>

    <!-- Context Header -->
    <div class="p-5 border-b border-space-800/50 relative">
      <div class="absolute left-4 top-6 w-2 h-2 rounded-full bg-neon-cyan glow-cyan"></div>
      <div class="pl-5 flex justify-between items-start">
        <div>
          <h2 class="font-bold text-white text-[13px] tracking-wider font-mono">CONVERSACIÓN</h2>
          <div class="flex items-center space-x-2 mt-1">
            <span class="w-1.5 h-1.5 rounded-full bg-neon-green"></span>
            <span class="text-[9px] text-neon-cyan/70 font-mono tracking-widest uppercase">MODO CONSULTA MULTI-AGENTE</span>
          </div>
        </div>
        <button 
          @click="clearChat"
          class="text-[9px] border border-space-700 hover:border-space-500 text-space-400 hover:text-slate-300 font-mono px-3 py-1.5 rounded transition-colors uppercase tracking-widest bg-space-900"
        >
          Limpiar
        </button>
      </div>
      
      <!-- File attachment indicator (if selected) -->
      <div v-if="selectedFile" class="mt-4 bg-[#0a192f] border border-neon-cyan/30 rounded-lg p-3 flex items-center space-x-3 shadow-inner">
        <Check class="w-4 h-4 text-neon-cyan shrink-0" />
        <div class="text-[11px] text-neon-cyan/90 font-mono truncate">
          Archivo de contexto cargado ({{ selectedFile.name }})
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="chatScroll" class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-6">
      <div 
        v-for="(msg, i) in messages" 
        :key="i"
        class="flex flex-col w-full"
      >
        <!-- User Bubble -->
        <template v-if="msg.role === 'user'">
          <div class="flex flex-col items-end max-w-[85%] self-end">
            <div class="flex items-center space-x-2 mb-2 text-neon-cyan">
              <span class="text-[10px] font-mono tracking-wider uppercase font-bold">USUARIO (TÚ)</span>
              <User class="w-3.5 h-3.5" />
            </div>
            <div class="bg-[#0a192f] border border-neon-cyan/50 rounded-xl rounded-tr-none px-5 py-4 text-sm text-cyan-50 shadow-[0_0_15px_-3px_rgba(0,229,255,0.15)] leading-relaxed">
              {{ msg.content }}
            </div>
          </div>
        </template>
        
        <!-- Assistant Bubble -->
        <template v-else>
          <div class="flex flex-col items-start max-w-[95%]">
            <div class="flex items-center space-x-2 mb-2">
              <div class="w-5 h-5 rounded-full border border-neon-green/50 flex items-center justify-center bg-neon-green/10 text-neon-green">
                <Bot class="w-3 h-3" />
              </div>
              <span class="text-[11px] font-bold text-white tracking-widest font-mono">A.T.E.N.E.A.</span>
              <span class="px-2 py-0.5 bg-neon-green/10 border border-neon-green/30 text-neon-green text-[8px] font-mono uppercase tracking-widest rounded shadow-sm">
                {{ msg.agentName || 'SUPERVISOR AGENT' }}
              </span>
            </div>
            <div class="w-full bg-[#030509] border border-neon-green/40 rounded-xl rounded-tl-none px-5 py-4 text-[13px] text-slate-300 leading-relaxed whitespace-pre-wrap shadow-[0_0_15px_-3px_rgba(0,255,157,0.1)]">
              {{ msg.content }}
            </div>
          </div>
        </template>
      </div>
      
      <!-- Typing indicator -->
      <div v-if="isDebating" class="flex flex-col items-start max-w-[90%]">
        <div class="flex items-center space-x-2 mb-2 opacity-70">
          <div class="w-5 h-5 rounded-full border border-neon-green/50 flex items-center justify-center bg-neon-green/10 text-neon-green">
            <Bot class="w-3 h-3" />
          </div>
          <span class="text-[11px] font-bold text-white tracking-widest font-mono">A.T.E.N.E.A.</span>
        </div>
        <div class="bg-[#030509] border border-neon-green/40 rounded-xl rounded-tl-none px-5 py-3 shadow-[0_0_15px_-3px_rgba(0,255,157,0.1)]">
          <div class="flex space-x-1 items-center h-4">
            <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce"></div>
            <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="p-4 border-t border-space-800 bg-[#060a11]">
      <form @submit.prevent="onSubmit" class="flex flex-col gap-3 relative">
        <div class="flex items-center gap-2">
          <!-- Custom Agent Dropdown -->
          <div class="relative" ref="agentDropdownRef">
            <button 
              type="button"
              @click="toggleAgentDropdown"
              :disabled="isDebating"
              data-test="agent-dropdown-btn"
              class="flex items-center justify-between w-40 bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 rounded px-3 py-1.5 text-[11px] font-mono text-cyan-50 shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] transition-all disabled:opacity-50"
            >
              <span class="truncate">{{ selectedAgentLabel }}</span>
              <ChevronDown class="w-3 h-3 text-neon-cyan ml-2 shrink-0" />
            </button>
            
            <div 
              v-if="isAgentDropdownOpen"
              class="absolute bottom-full left-0 mb-2 w-48 bg-space-950 border border-neon-cyan/50 rounded shadow-[0_0_15px_rgba(0,229,255,0.15)] overflow-hidden z-50 font-mono text-xs"
            >
              <div class="px-3 py-1.5 bg-space-900 text-neon-cyan/70 text-[9px] uppercase tracking-wider border-b border-neon-cyan/30">
                Seleccionar Agente
              </div>
              <div class="max-h-[200px] overflow-y-auto custom-scrollbar">
                <button 
                  v-for="agent in agentsList" 
                  :key="agent.value"
                  type="button"
                  @click="selectAgent(agent.value)"
                  data-test="agent-option"
                  class="w-full text-left px-3 py-2 transition-colors flex items-center justify-between"
                  :class="selectedAgent === agent.value ? 'bg-neon-cyan/10 text-neon-cyan' : 'text-slate-300 hover:bg-space-800 hover:text-cyan-200'"
                >
                  <span class="font-bold text-[10px] md:text-[11px]">{{ agent.label }}</span>
                  <span v-if="selectedAgent === agent.value" class="w-1.5 h-1.5 rounded-full bg-neon-cyan glow-cyan"></span>
                </button>
              </div>
            </div>
          </div>

          <label class="cursor-pointer text-space-400 hover:text-neon-cyan transition-colors flex items-center justify-center px-3 py-1.5 border border-cyan-900/50 rounded bg-[#030509] hover:bg-space-800 shadow-[0_0_10px_-2px_rgba(0,229,255,0.05)] hover:border-neon-cyan/50" title="Adjuntar archivo">
            <input type="file" @change="handleFileChange" class="hidden" data-test="file-input" />
            <Paperclip class="w-4 h-4" />
          </label>
        </div>
        
        <div class="relative flex items-center w-full">
          <textarea 
            v-model="inputMsg"
            placeholder="Escribe tu consulta o pulsa el micrófono..."
            rows="1"
            class="w-full bg-[#030509] border border-space-700 rounded-lg pl-4 pr-12 py-[3px] text-sm text-slate-200 focus:outline-none focus:border-neon-cyan transition-all placeholder:text-[11px] placeholder-space-600 font-mono shadow-inner resize-none custom-scrollbar min-h-[44px]"
            :disabled="isDebating"
            @keydown.enter.prevent="onSubmit"
          ></textarea>
          
          <button 
            type="submit"
            :disabled="!inputMsg.trim() || isDebating"
            class="absolute right-2 p-1.5 bg-[#00e5ff] text-[#060a11] hover:bg-cyan-400 disabled:opacity-50 disabled:hover:bg-[#00e5ff] transition-colors rounded shadow-[0_0_10px_rgba(0,229,255,0.3)]"
          >
            <SendHorizontal class="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
