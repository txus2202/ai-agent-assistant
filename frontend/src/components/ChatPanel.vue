<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { SendHorizontal, Paperclip, Check, User, Bot, ChevronDown, Copy, Eye, Brain, X, Edit3, GitFork, Flag } from '@lucide/vue'
import { useDebateStore, type ChatMessage } from '../stores/debate'
import DiagramModal from './DiagramModal.vue'
import { cleanTextForTts, splitTextIntoTtsChunks } from '../utils/ttsFilter'
import { parseMessageContent } from '../utils/messageParser'

const props = defineProps<{
  messages: ChatMessage[]
  isDebating: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-mic'): void
}>()

const store = useDebateStore()
const chatScroll = ref<HTMLElement | null>(null)
const isDiagramModalOpen = ref(false)
const activeDiagramCode = ref('')
const activeDiagramTitle = ref('Diagrama de Arquitectura')
const copiedDiagramIndex = ref<number | null>(null)

const openDiagramModal = (code: string, title?: string) => {
  activeDiagramCode.value = code
  activeDiagramTitle.value = title || 'Diagrama de Arquitectura'
  isDiagramModalOpen.value = true
}

const closeDiagramModal = () => {
  isDiagramModalOpen.value = false
}

const copyChatDiagramCode = async (code: string, blockIndex: number) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedDiagramIndex.value = blockIndex
    setTimeout(() => {
      if (copiedDiagramIndex.value === blockIndex) {
        copiedDiagramIndex.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy diagram code:', err)
  }
}



const agentsList = computed(() => {
  const fromStore = (store.agents || []).map(a => ({
    value: a.role,
    label: a.name,
    colorHex: a.color_hex
  }))
  if (fromStore.some(a => a.value === 'supervisor')) {
    return fromStore
  }
  return [
    { value: 'supervisor', label: 'Atenea', colorHex: '#f59e0b' },
    ...fromStore
  ]
})

const selectedAgent = ref(store.selectedAgent || 'supervisor')

watch(() => store.selectedAgent, (newAgent) => {
  if (newAgent) {
    selectedAgent.value = newAgent
  }
})

const selectedFiles = ref<File[]>([])
const isAgentDropdownOpen = ref(false)
const agentDropdownRef = ref<HTMLElement | null>(null)
const selectedAgentLabel = computed(() => {
  return agentsList.value.find(a => a.value === selectedAgent.value)?.label || 'Atenea'
})

const toggleAgentDropdown = () => {
  if (props.isDebating) return
  isAgentDropdownOpen.value = !isAgentDropdownOpen.value
}

const selectAgent = (value: string) => {
  selectedAgent.value = value
  store.selectedAgent = value
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
  if (typeof store.onTtsChunkReady === 'function') {
    store.onTtsChunkReady((chunk: string, role?: string) => {
      queueTtsSentence(chunk, role)
    })
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideAgent)
})

// TTS Queue logic for gapless sentence-by-sentence playback
let ttsTextQueue: string[] = []
let ttsAudioQueue: ArrayBuffer[] = []
let isPrefetching = false
let isPlayingAudio = false

// Watch store.isTtsPlaying to abort playback
watch(() => store.isTtsPlaying, (isPlaying) => {
  if (!isPlaying) {
    ttsTextQueue = []
    ttsAudioQueue = []
    isPrefetching = false
    isPlayingAudio = false
  }
})

const queueTtsSentence = (sentence: string, role?: string) => {
  if (!store.isVoiceOutputEnabled || !sentence) return
  const clean = cleanTextForTts(sentence)
  if (!clean) return

  store.isTtsPlaying = true
  if (role) {
    store.activeTtsRole = role
  }

  const chunks = splitTextIntoTtsChunks(clean)
  ttsTextQueue.push(...chunks)

  if (!isPrefetching) {
    prefetchTtsQueue()
  }
}

const playVoiceResponse = async (text: string, role?: string) => {
  if (!store.isVoiceOutputEnabled || !text) return

  // Clean text from diagrams and markdown for natural voice synthesis
  const cleanText = cleanTextForTts(text)
  if (!cleanText) return

  // Set store state
  store.isTtsPlaying = true
  if (role) {
    store.activeTtsRole = role
  }

  // Split by punctuation (., ?, !, \n, ,, ;, :) for immediate low-latency Time-To-First-Audio
  const sentences = splitTextIntoTtsChunks(cleanText)

  ttsTextQueue.push(...sentences)

  if (!isPrefetching) {
    prefetchTtsQueue()
  }
}

const prefetchTtsQueue = async () => {
  if (ttsTextQueue.length === 0) {
    isPrefetching = false
    return
  }
  
  isPrefetching = true
  const sentence = ttsTextQueue.shift()!
  
  try {
    const response = await fetch('/api/audio/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: sentence, add_silence: false })
    })
    
    if (response.ok) {
      // If the user pressed stop while we were fetching, discard this result
      if (!store.isTtsPlaying) {
        isPrefetching = false
        return
      }

      const audioBuffer = await response.arrayBuffer()
      ttsAudioQueue.push(audioBuffer)
      
      // If audio player is idle, start playing immediately
      if (store.isTtsPlaying && !isPlayingAudio) {
        playNextAudio()
      }
    }
  } catch (e) {
    console.error("Error synthesizing speech:", e)
  }
  
  // Fetch next sentence immediately
  if (store.isTtsPlaying) {
    prefetchTtsQueue()
  } else {
    isPrefetching = false
  }
}

const playNextAudio = async () => {
  if (isPlayingAudio) return

  if (ttsAudioQueue.length === 0) {
    if (ttsTextQueue.length === 0 && !isPrefetching) {
      // Completely done playing all queued TTS
      store.stopTts()
    }
    return
  }
  
  if (!store.isTtsPlaying) return
  
  isPlayingAudio = true
  const nextChunk = ttsAudioQueue.shift()!
  
  try {
    if (store.playTtsAudioChunk) {
      await store.playTtsAudioChunk(nextChunk)
    }
  } catch (e) {
    console.error("Play error:", e)
  } finally {
    isPlayingAudio = false
    if (store.isTtsPlaying) {
      playNextAudio()
    }
  }
}

watch(() => props.messages.length, (newLen, oldLen) => {
  if (newLen > oldLen) {
    const lastMsg = props.messages[newLen - 1]
    if (newLen === oldLen + 1 && lastMsg && lastMsg.role === 'assistant' && !store.streamingMessageId && !lastMsg.isStreaming) {
      // Determine the agent role for TTS voice synthesis (from agentRole or agentName)
      const match = lastMsg.content.match(/^\[(.*?)\]\s/)
      const role = lastMsg.agentRole || lastMsg.agentName || (match ? match[1] : undefined)
      playVoiceResponse(lastMsg.content, role)
    }
  }
})

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFiles.value = [...selectedFiles.value, ...Array.from(target.files)]
    target.value = ''
  }
}

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

const clearFiles = () => {
  selectedFiles.value = []
}

const selectedTargetAgents = ref<string[]>([])
const chatInputRef = ref<HTMLTextAreaElement | null>(null)

const selectableAgents = computed(() => {
  return (store.agents || []).map(a => ({
    value: a.role,
    label: a.name,
    colorHex: a.color_hex || '#00e5ff'
  }))
})

watch(() => store.hitlTargetAgents, (newVal) => {
  if (newVal) {
    selectedTargetAgents.value = [...newVal]
  }
}, { deep: true, immediate: true })

const toggleTargetAgent = (role: string) => {
  if (typeof store.toggleHitlTargetAgent === 'function') {
    store.toggleHitlTargetAgent(role)
  }
  if (selectedTargetAgents.value.includes(role)) {
    selectedTargetAgents.value = selectedTargetAgents.value.filter(r => r !== role)
  } else {
    selectedTargetAgents.value.push(role)
  }
}

const isTargetSelected = (role: string) => {
  if (store.hitlTargetAgents && store.hitlTargetAgents.length > 0) {
    return store.hitlTargetAgents.includes(role)
  }
  return selectedTargetAgents.value.includes(role)
}

const handleHitlApprove = () => {
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  store.submitHitlDecision('approve', '', targets)
  selectedTargetAgents.value = []
}

const handleHitlDivert = () => {
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  if (targets.length === 0) {
    alert('Por favor selecciona al menos un agente en los chips para desviar la tarea.')
    return
  }
  store.submitHitlDecision('divert', store.draftMessage.trim(), targets)
  store.draftMessage = ''
  selectedTargetAgents.value = []
}

const handleHitlFinish = () => {
  store.submitHitlDecision('finish')
  selectedTargetAgents.value = []
}

const handleHitlReject = () => {
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  store.submitHitlDecision('reject', '', targets)
  selectedTargetAgents.value = []
}

const focusRefineInput = () => {
  store.stopTts()
  nextTick(() => {
    chatInputRef.value?.focus()
  })
}

const onSubmit = async () => {
  if (store.isHitlRequired) {
    if (!store.draftMessage.trim()) {
      focusRefineInput()
      return
    }
    store.submitHitlDecision('refine', store.draftMessage.trim(), selectedTargetAgents.value)
    store.draftMessage = ''
    selectedTargetAgents.value = []
    return
  }

  if (!store.draftMessage.trim() || props.isDebating) return
  
  if (store.isVoiceOutputEnabled) {
    store.unlockAudioContext()
  }
  
  let attachmentUrls: string[] = []
  if (selectedFiles.value.length > 0) {
    try {
      attachmentUrls = await Promise.all(selectedFiles.value.map(file => store.uploadFile(file)))
    } catch (e) {
      console.error('Failed to upload file:', e)
      alert('Error uploading file. Please try again.')
      return
    }
  }

  let attachmentParam: string | string[] | null = null
  if (attachmentUrls.length === 1 && attachmentUrls[0]) {
    attachmentParam = attachmentUrls[0]
  } else if (attachmentUrls.length > 1) {
    attachmentParam = attachmentUrls
  }

  store.startDebate(store.draftMessage, selectedAgent.value, attachmentParam)
  
  store.draftMessage = ''
  selectedFiles.value = []
}

const clearChat = () => {
  if (confirm('¿Seguro que deseas limpiar la conversación actual?')) {
    if (typeof store.clearSession === 'function') {
      store.clearSession()
    } else {
      store.messages.splice(0, store.messages.length)
      store.rawEvents.splice(0, store.rawEvents.length)
    }
  }
}

const handleLearnSession = async () => {
  if (props.isDebating || store.isLearningSession) return
  if (typeof store.learnSession === 'function') {
    await store.learnSession(store.currentSessionId)
  }
}

// Auto-scroll to the start of the last message
watch(() => props.messages.length, async (newLen) => {
  await nextTick()
  if (chatScroll.value && newLen > 0) {
    // Find all message blocks
    const messageBlocks = chatScroll.value.querySelectorAll('.message-block')
    if (messageBlocks.length > 0) {
      // Get the last message block
      const lastMessageEl = messageBlocks[messageBlocks.length - 1] as HTMLElement
      // Scroll it into view smoothly, aligning it to the start of the view
      lastMessageEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
})

const setActiveTab = (_tab: 'chat' | 'observability') => {
  // Observability is now located in the right column alongside AgentTopology
}

defineExpose({
  onSubmit,
  setActiveTab
})
</script>

<template>
  <div class="flex flex-col h-full bg-[#060a11] border-r border-space-800 font-sans">
    <!-- Context Header -->
    <div class="p-3.5 md:p-5 border-b border-space-800/50 relative">
      <div class="absolute left-3.5 md:left-4 top-5 md:top-6 w-2 h-2 rounded-full bg-neon-cyan glow-cyan"></div>
      <div class="pl-5 flex justify-between items-start gap-2">
        <div class="min-w-0">
          <h2 class="font-bold text-white text-xs md:text-[13px] tracking-wider font-mono">CONVERSACIÓN</h2>
          <div class="flex items-center space-x-2 mt-1">
            <span class="w-1.5 h-1.5 rounded-full bg-neon-green shrink-0"></span>
            <span class="text-[9px] text-neon-cyan/70 font-mono tracking-widest uppercase truncate">MODO CONSULTA MULTI-AGENTE</span>
          </div>
        </div>
        <div class="flex items-center space-x-1.5 md:space-x-2 shrink-0">
          <!-- Learn Button -->
          <button 
            @click="handleLearnSession"
            :disabled="store.isLearningSession || messages.length === 0 || props.isDebating"
            class="text-[9px] border border-cyan-800/80 hover:border-neon-cyan text-neon-cyan font-mono px-2.5 md:px-3 py-1.5 min-h-[34px] md:min-h-0 rounded transition-all uppercase tracking-widest bg-[#040e1a] hover:bg-neon-cyan/15 flex items-center space-x-1.5 disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_10px_rgba(0,229,255,0.08)] cursor-pointer"
            title="Pedir a Metis que sintetice y aprenda la sesión en Obsidian Vault"
            data-test="learn-session-btn"
          >
            <Brain class="w-3.5 h-3.5" :class="{ 'animate-pulse': store.isLearningSession }" />
            <span>{{ store.isLearningSession ? 'Asimilando...' : 'Aprender' }}</span>
          </button>

          <!-- Clear Chat -->
          <button 
            @click="clearChat"
            class="text-[9px] border border-space-700 hover:border-space-500 text-space-400 hover:text-slate-300 font-mono px-2.5 md:px-3 py-1.5 min-h-[34px] md:min-h-0 rounded transition-colors uppercase tracking-widest bg-space-900"
          >
            Limpiar
          </button>
        </div>
      </div>
      
      <!-- Learning status notification banner -->
      <div 
        v-if="store.learningStatusMessage" 
        class="mt-3 bg-[#031525] border border-neon-cyan/40 rounded-lg p-3 flex items-center justify-between shadow-[0_0_15px_rgba(0,229,255,0.15)] text-xs font-mono text-cyan-200 animate-fade-in"
        data-test="learning-status-banner"
      >
        <div class="flex items-center space-x-2.5">
          <Brain class="w-4 h-4 text-neon-cyan shrink-0" />
          <span>{{ store.learningStatusMessage }}</span>
        </div>
        <button 
          @click="store.learningStatusMessage = null"
          class="text-space-400 hover:text-white p-1 rounded hover:bg-space-800 transition-colors cursor-pointer"
          title="Cerrar notificación"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- File attachments indicator (if files selected) -->
      <div v-if="selectedFiles.length > 0" class="mt-4 bg-[#0a192f] border border-neon-cyan/30 rounded-lg p-3 flex flex-col gap-2 shadow-inner" data-test="file-attachments-container">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <Check class="w-4 h-4 text-neon-cyan shrink-0" />
            <span class="text-[11px] text-neon-cyan/90 font-mono font-bold tracking-wide">
              {{ selectedFiles.length === 1 ? `Archivo de contexto cargado (${selectedFiles[0]?.name})` : `${selectedFiles.length} archivos cargados para Metis` }}
            </span>
          </div>
          <button 
            type="button" 
            @click="clearFiles" 
            class="text-[9px] font-mono text-space-400 hover:text-red-400 uppercase tracking-wider transition-colors cursor-pointer"
            data-test="clear-files-btn"
          >
            Quitar todos
          </button>
        </div>

        <div class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto custom-scrollbar pt-1">
          <div 
            v-for="(file, index) in selectedFiles" 
            :key="index"
            class="bg-[#030509] border border-neon-cyan/40 px-2 py-1 rounded text-[10px] font-mono text-cyan-200 flex items-center space-x-1.5 shadow-sm"
            data-test="attached-file-chip"
          >
            <span class="truncate max-w-[160px]">{{ file.name }}</span>
            <button 
              type="button" 
              @click="removeFile(index)" 
              class="text-space-400 hover:text-red-400 transition-colors cursor-pointer p-0.5 rounded hover:bg-space-800"
              title="Quitar archivo"
              data-test="remove-file-btn"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="chatScroll" class="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar p-3.5 sm:p-5 space-y-6 min-w-0 max-w-full">
      <div 
        v-for="(msg, i) in messages" 
        :key="i"
        class="flex flex-col w-full message-block min-w-0 max-w-full"
      >
        <!-- User Bubble -->
        <template v-if="msg.role === 'user'">
          <div class="flex flex-col items-end max-w-[85%] self-end min-w-0">
            <div class="flex items-center space-x-2 mb-2 text-neon-cyan">
              <span class="text-[10px] font-mono tracking-wider uppercase font-bold">USUARIO (TÚ)</span>
              <User class="w-3.5 h-3.5" />
            </div>
            <div class="bg-[#0a192f] border border-neon-cyan/50 rounded-xl rounded-tr-none px-4 py-3 sm:px-5 sm:py-4 text-sm text-cyan-50 shadow-[0_0_15px_-3px_rgba(0,229,255,0.15)] leading-relaxed break-words [overflow-wrap:break-word] min-w-0 max-w-full overflow-hidden">
              {{ msg.content }}
            </div>
          </div>
        </template>
        
        <!-- Assistant Bubble -->
        <template v-else>
          <div class="flex flex-col items-start max-w-[95%] min-w-0 w-full">
            <div class="flex items-center space-x-2 mb-2">
              <div 
                class="w-5 h-5 rounded-full border flex items-center justify-center transition-colors"
                :style="msg.colorHex ? { borderColor: `${msg.colorHex}80`, backgroundColor: `${msg.colorHex}1a`, color: msg.colorHex } : {}"
                :class="!msg.colorHex ? 'border-neon-green/50 bg-neon-green/10 text-neon-green' : ''"
              >
                <Bot class="w-3 h-3" />
              </div>
              <span class="text-[11px] font-bold text-white tracking-widest font-mono">A.T.E.N.E.A.</span>
              <span 
                class="px-2 py-0.5 border text-[8px] font-mono uppercase tracking-widest rounded shadow-sm transition-colors"
                :style="msg.colorHex ? { borderColor: `${msg.colorHex}4d`, backgroundColor: `${msg.colorHex}1a`, color: msg.colorHex } : {}"
                :class="!msg.colorHex ? 'bg-neon-green/10 border-neon-green/30 text-neon-green' : ''"
              >
                {{ msg.agentName || 'ATENEA' }}
              </span>
              
              <!-- Stop TTS Button -->
              <button 
                v-if="store.isTtsPlaying && i === messages.length - 1"
                @click="store.stopTts()"
                class="ml-2 px-2 py-0.5 bg-red-900/40 hover:bg-red-900/80 border border-red-500/50 text-red-400 text-[9px] font-mono uppercase tracking-widest rounded shadow-sm flex items-center space-x-1 transition-colors cursor-pointer"
                title="Detener lectura de este mensaje"
              >
                <div class="w-1.5 h-1.5 bg-red-500 rounded-sm"></div>
                <span>Silenciar</span>
              </button>
            </div>
            <div 
              class="w-full bg-[#030509] border rounded-xl rounded-tl-none px-4 py-3 sm:px-5 sm:py-4 text-[13px] text-slate-300 leading-relaxed transition-colors flex flex-col gap-3 min-w-0 max-w-full overflow-hidden"
              :style="msg.colorHex ? { borderColor: `${msg.colorHex}4d`, boxShadow: `0 0 15px -3px ${msg.colorHex}1a` } : {}"
              :class="!msg.colorHex ? 'border-neon-green/40 shadow-[0_0_15px_-3px_rgba(0,255,157,0.1)]' : ''"
            >
              <template v-for="(block, blockIdx) in parseMessageContent(msg.content)" :key="blockIdx">
                <!-- Text block -->
                <div v-if="block.type === 'text'" class="whitespace-pre-wrap leading-relaxed break-words [overflow-wrap:break-word] min-w-0 max-w-full">
                  {{ block.content }}
                </div>

                <!-- Mermaid Diagram Card -->
                <div 
                  v-else-if="block.type === 'mermaid'"
                  data-test="chat-diagram-card"
                  class="my-2 bg-[#050a14] border border-cyan-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.1)]"
                >
                  <!-- Card Header with Actions -->
                  <div class="flex items-center justify-end px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30 gap-2">
                    <!-- Copy Button -->
                      <button
                        type="button"
                        @click="copyChatDiagramCode(block.content, i * 100 + blockIdx)"
                        data-test="chat-diagram-copy-btn"
                        class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-[11px] font-mono text-cyan-200 hover:text-white transition-colors cursor-pointer"
                        title="Copiar al portapapeles"
                      >
                        <Check v-if="copiedDiagramIndex === (i * 100 + blockIdx)" class="w-3 h-3 text-emerald-400" />
                        <Copy v-else class="w-3 h-3" />
                        <span>{{ copiedDiagramIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar' }}</span>
                      </button>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openDiagramModal(block.content, `Diagrama de ${msg.agentName || 'Arquitectura'}`)"
                        data-test="chat-diagram-view-btn"
                        class="flex items-center gap-1.5 px-3 py-1 rounded bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-[11px] font-mono font-bold text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer"
                        title="Ver diagrama"
                      >
                        <Eye class="w-3 h-3" />
                        <span>Ver</span>
                      </button>
                    </div>

                  <!-- Code snippet preview -->
                  <pre class="p-3.5 bg-[#020408] font-mono text-xs text-cyan-200/90 overflow-x-auto custom-scrollbar max-h-48 border-t border-space-900/50"><code>{{ block.content }}</code></pre>
                </div>
              </template>
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
      <!-- Integrated HITL Control Card in Chat -->
      <div 
        v-if="store.isHitlRequired" 
        data-test="hitl-chat-card"
        class="mb-3 p-3.5 bg-[#080d1a] border border-neon-amber/60 rounded-xl shadow-[0_0_20px_rgba(245,158,11,0.15)] flex flex-col gap-2.5 animate-fade-in"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-neon-amber animate-pulse"></span>
            <span class="text-xs font-mono font-bold text-neon-amber tracking-wider uppercase">
              Punto de Control (HITL)
            </span>
          </div>
          <span class="text-[10px] font-mono text-slate-400">
            Valida o redirige el debate
          </span>
        </div>

        <!-- Target Agents Chips Selector -->
        <div v-if="selectableAgents.length > 0" class="flex flex-col gap-1.5 pt-1">
          <span class="text-[10px] font-mono text-slate-400">Redirigir a agentes específicos (opcional):</span>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="agent in selectableAgents"
              :key="agent.value"
              type="button"
              @click="toggleTargetAgent(agent.value)"
              data-test="hitl-target-chip"
              class="px-2 py-0.5 rounded text-[10px] font-mono border transition-all flex items-center gap-1.5 cursor-pointer"
              :style="isTargetSelected(agent.value)
                ? { borderColor: agent.colorHex, backgroundColor: `${agent.colorHex}25`, color: '#ffffff' }
                : { borderColor: `${agent.colorHex}40`, backgroundColor: 'transparent', color: '#94a3b8' }"
            >
              <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ backgroundColor: agent.colorHex }"></span>
              <span>{{ agent.label }}</span>
            </button>
          </div>
        </div>

        <!-- Quick Action Buttons (2 Rows: Row 1 = Aceptar, Rechazar, Finalizar | Row 2 = Refinar, Desviar) -->
        <div class="flex flex-col gap-1.5 pt-1 w-full">
          <!-- Row 1: Aceptar, Rechazar y Finalizar -->
          <div class="grid grid-cols-3 gap-1.5 w-full">
            <button
              type="button"
              @click="handleHitlApprove"
              data-test="hitl-approve-btn"
              class="h-8.5 w-full bg-emerald-500/15 hover:bg-emerald-500/30 border border-emerald-500/60 text-emerald-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Aceptar dictamen y consolidar"
            >
              <Check class="w-3.5 h-3.5 shrink-0" />
              <span>Aceptar</span>
            </button>
            <button
              type="button"
              @click="handleHitlReject"
              data-test="hitl-reject-btn"
              class="h-8.5 w-full bg-red-500/15 hover:bg-red-500/30 border border-red-500/60 text-red-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Rechazar y abortar deliberación"
            >
              <X class="w-3.5 h-3.5 shrink-0" />
              <span>Rechazar</span>
            </button>
            <button
              type="button"
              @click="handleHitlFinish"
              data-test="hitl-finish-btn"
              class="h-8.5 w-full bg-purple-500/15 hover:bg-purple-500/30 border border-purple-500/60 text-purple-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Concluir el debate anticipadamente y consolidar dictamen final"
            >
              <Flag class="w-3.5 h-3.5 shrink-0" />
              <span>Finalizar</span>
            </button>
          </div>

          <!-- Row 2: Refinar y Desviar -->
          <div class="grid grid-cols-2 gap-1.5 w-full">
            <button
              type="button"
              @click="focusRefineInput"
              data-test="hitl-refine-btn"
              class="h-8.5 w-full bg-neon-amber/15 hover:bg-neon-amber/30 border border-neon-amber/60 text-neon-amber font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Refinar con nuevas instrucciones"
            >
              <Edit3 class="w-3.5 h-3.5 shrink-0" />
              <span>Refinar</span>
            </button>
            <button
              type="button"
              @click="handleHitlDivert"
              data-test="hitl-divert-btn"
              class="h-8.5 w-full bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-500/60 text-cyan-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Desviar deliberación a los agentes seleccionados arriba"
            >
              <GitFork class="w-3.5 h-3.5 shrink-0" />
              <span>Desviar</span>
            </button>
          </div>
        </div>
      </div>

      <form @submit.prevent="onSubmit" class="flex flex-col gap-2.5 md:gap-3 relative">
        <div class="flex items-center gap-2">
          <!-- Custom Agent Dropdown -->
          <div class="relative" ref="agentDropdownRef">
            <button 
              type="button"
              @click="toggleAgentDropdown"
              :disabled="isDebating && !store.isHitlRequired"
              data-test="agent-dropdown-btn"
              class="flex items-center justify-between w-40 min-h-[36px] md:min-h-0 bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 rounded px-3 py-1.5 text-[11px] font-mono text-cyan-50 shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] transition-all disabled:opacity-50"
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
                  class="w-full text-left px-3 py-2.5 md:py-2 transition-colors flex items-center justify-between"
                  :class="selectedAgent === agent.value ? 'bg-neon-cyan/10 text-neon-cyan' : 'text-slate-300 hover:bg-space-800 hover:text-cyan-200'"
                >
                  <span class="flex items-center space-x-2">
                    <span 
                      class="w-1.5 h-1.5 rounded-full shrink-0" 
                      :style="agent.colorHex ? { backgroundColor: agent.colorHex } : {}"
                    ></span>
                    <span class="font-bold text-[10px] md:text-[11px]">{{ agent.label }}</span>
                  </span>
                  <span v-if="selectedAgent === agent.value" class="w-1.5 h-1.5 rounded-full bg-neon-cyan glow-cyan"></span>
                </button>
              </div>
            </div>
          </div>

          <label 
            v-if="selectedAgent === 'learning'" 
            for="chat-file-upload" 
            class="cursor-pointer text-space-400 hover:text-neon-cyan transition-colors flex items-center justify-center px-3 py-1.5 min-h-[36px] md:min-h-0 border border-cyan-900/50 rounded bg-[#030509] hover:bg-space-800 shadow-[0_0_10px_-2px_rgba(0,229,255,0.05)] hover:border-neon-cyan/50" 
            title="Adjuntar PDF, Markdown o Imagen para Metis"
          >
            <span class="sr-only">Adjuntar archivo</span>
            <input 
              id="chat-file-upload" 
              type="file" 
              multiple
              accept=".pdf,.md,.markdown,.png,.jpg,.jpeg,.webp" 
              @change="handleFileChange" 
              class="hidden" 
              data-test="file-input" 
            />
            <Paperclip class="w-4 h-4" />
          </label>
        </div>
        
        <div class="flex items-end gap-2 w-full">
          <div class="relative flex items-center flex-1">
            <label for="chat-message-input" class="sr-only">Mensaje</label>
            <textarea 
              id="chat-message-input"
              ref="chatInputRef"
              v-model="store.draftMessage"
              :placeholder="store.isHitlRequired ? 'Introduce tus instrucciones de refinamiento...' : 'Escribe tu consulta...'"
              rows="3"
              class="w-full bg-[#030509] border rounded-xl pl-3.5 md:pl-4 pr-12 py-3 text-sm text-slate-200 focus:outline-none transition-all placeholder:text-[11px] placeholder-space-600 font-mono shadow-inner resize-none custom-scrollbar min-h-[76px] sm:min-h-[88px]"
              :class="store.isHitlRequired ? 'border-neon-amber/60 focus:border-neon-amber focus:ring-1 focus:ring-neon-amber/50' : 'border-space-700 focus:border-neon-cyan'"
              :disabled="isDebating && !store.isHitlRequired"
              @keydown.enter.prevent="onSubmit"
            ></textarea>
            
            <button 
              type="submit"
              data-test="chat-send-btn"
              :disabled="!store.draftMessage.trim() || (isDebating && !store.isHitlRequired)"
              class="absolute right-2.5 bottom-2.5 p-2 min-w-[36px] min-h-[36px] flex items-center justify-center bg-[#00e5ff] text-[#060a11] hover:bg-cyan-400 disabled:opacity-50 disabled:hover:bg-[#00e5ff] transition-all rounded-lg shadow-[0_0_10px_rgba(0,229,255,0.3)] cursor-pointer"
              :title="store.isHitlRequired ? 'Enviar refinamiento' : 'Enviar mensaje'"
            >
              <SendHorizontal class="w-4 h-4 md:w-5 md:h-5" />
            </button>
          </div>
        </div>
      </form>
    </div>

    <!-- Diagram Modal Visualizer -->
    <DiagramModal
      :is-open="isDiagramModalOpen"
      :code="activeDiagramCode"
      :title="activeDiagramTitle"
      @close="closeDiagramModal"
    />
  </div>
</template>
