<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { 
  SendHorizontal, 
  Paperclip, 
  Check, 
  User, 
  Bot, 
  ChevronDown, 
  Copy, 
  Eye, 
  Brain, 
  X, 
  Edit3, 
  GitFork, 
  Download,
  Code2,
  ImageIcon,
  FileText,
  Printer,
  Square,
  Sparkles,
  RotateCcw,
  Info,
  Network,
  MonitorPlay,
  Globe,
  FileCode,
  ArrowDown,
  ArrowUp
} from '@lucide/vue'
import { useDebateStore, type ChatMessage } from '../stores/debate'
import DiagramModal from './tools/DiagramModal.vue'
import CodeModal from './tools/CodeModal.vue'
import ImageModal from './tools/ImageModal.vue'
import DocumentModal from './tools/DocumentModal.vue'
import PresentationModal from './tools/PresentationModal.vue'
import {
  downloadPresentationHtml,
  downloadPresentationMarkdown,
  exportPresentationPptx
} from '../utils/presentationExporter'
import { parsePresentation } from '../utils/slideParser'
import { cleanTextForTts, splitTextIntoTtsChunks } from '../utils/ttsFilter'
import { parseMessageContent, getLanguageExtension } from '../utils/messageParser'
import { getMimeTypeForExtension } from '../utils/mimeHelper'
import {
  downloadMarkdownFile,
  exportDocumentToPdf,
  extractDocumentTitle,
  renderMarkdownToHtml
} from '../utils/markdownRenderer'

const props = defineProps<{
  messages: ChatMessage[]
  isDebating: boolean
}>()

defineEmits<{
  (e: 'toggle-mic'): void
}>()

const store = useDebateStore()
const chatScroll = ref<HTMLElement | null>(null)
const isChatScrollable = ref(false)
const scrollDirection = ref<'up' | 'down'>('up')
let scrollResizeObserver: ResizeObserver | null = null

const updateChatScrollState = () => {
  const el = chatScroll.value
  if (!el) {
    isChatScrollable.value = false
    return
  }
  const maxScroll = el.scrollHeight - el.clientHeight
  // Content is scrollable if overflow exceeds a small threshold
  const canScroll = maxScroll > 15
  isChatScrollable.value = canScroll

  if (canScroll) {
    // If in the upper half (< maxScroll / 2), the button points down to scroll to the bottom.
    // If in the lower half (>= maxScroll / 2), the button points up to scroll to the top.
    scrollDirection.value = el.scrollTop < maxScroll / 2 ? 'down' : 'up'
  }
}

const handleScrollToggle = () => {
  const el = chatScroll.value
  if (!el) return
  if (scrollDirection.value === 'down') {
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      el.scrollTop = el.scrollHeight
    }
  } else {
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      el.scrollTop = 0
    }
  }
}

// Diagram Modal State
const isDiagramModalOpen = ref(false)
const activeDiagramCode = ref('')
const activeDiagramTitle = ref('Diagrama')
const copiedDiagramIndex = ref<number | null>(null)

// Code Modal State
const isCodeModalOpen = ref(false)
const activeCode = ref('')
const activeCodeLanguage = ref('code')
const activeCodeExtension = ref('')
const activeCodeTitle = ref('Visualizador de Código')
const copiedCodeIndex = ref<number | null>(null)

// Image Modal State
const isImageModalOpen = ref(false)
const activeImageUrl = ref('')
const activeImageAlt = ref('Recurso visual')
const activeImageTitle = ref('Visualizador de Imagen')

// Document Modal State (Calíope / document_viewer)
const isDocumentModalOpen = ref(false)
const activeDocContent = ref('')
const activeDocTitle = ref('Documento Técnico')
const copiedDocIndex = ref<number | null>(null)

// Presentation Modal State (Calíope / presentation_viewer)
const isPresentationModalOpen = ref(false)
const activePresentationContent = ref('')
const activePresentationTitle = ref('Presentación')
const copiedPresentationIndex = ref<number | null>(null)
const activePresentationDownloadMenu = ref<number | null>(null)

const togglePresentationDownloadMenu = (index: number) => {
  activePresentationDownloadMenu.value = activePresentationDownloadMenu.value === index ? null : index
}

const closePresentationDownloadMenu = () => {
  activePresentationDownloadMenu.value = null
}

const openPresentationModal = (content: string, title?: string) => {
  activePresentationContent.value = content
  activePresentationTitle.value = title || 'Presentación'
  isPresentationModalOpen.value = true
}

const closePresentationModal = () => {
  isPresentationModalOpen.value = false
  activePresentationContent.value = ''
  activePresentationTitle.value = 'Presentación'
}

const copyPresentationContent = async (content: string, index: number) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedPresentationIndex.value = index
    setTimeout(() => {
      if (copiedPresentationIndex.value === index) {
        copiedPresentationIndex.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy presentation content:', err)
  }
}

const downloadChatPresentation = (content: string, title?: string) => {
  closePresentationDownloadMenu()
  const parsed = parsePresentation(content)
  downloadPresentationHtml(parsed, title || parsed.title)
}

const downloadChatPresentationPptx = async (content: string, title?: string) => {
  closePresentationDownloadMenu()
  const parsed = parsePresentation(content)
  await exportPresentationPptx(parsed, title || parsed.title)
}

const downloadChatPresentationMarkdown = (content: string, title?: string) => {
  closePresentationDownloadMenu()
  downloadPresentationMarkdown(content, title)
}

const openDocumentModal = (content: string, title?: string) => {
  activeDocContent.value = content
  activeDocTitle.value = title || extractDocumentTitle(content, 'Documento Técnico')
  isDocumentModalOpen.value = true
}

const closeDocumentModal = () => {
  isDocumentModalOpen.value = false
  activeDocContent.value = ''
  activeDocTitle.value = 'Documento Técnico'
}

const agentHasDocumentViewer = (agentName?: string): boolean => {
  if (!agentName) return false
  const lower = agentName.toLowerCase()
  if (lower.includes('caliope') || lower.includes('calíope')) return true
  const agent = store.agents?.find(a => 
    a.name?.toLowerCase() === lower || 
    a.role?.toLowerCase() === lower
  )
  return agent?.tools?.includes('document_viewer') ?? false
}

const copyDocContent = async (content: string, index: number) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedDocIndex.value = index
    setTimeout(() => {
      if (copiedDocIndex.value === index) {
        copiedDocIndex.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy document content:', err)
  }
}

const openDiagramModal = (code: string, title?: string) => {
  activeDiagramCode.value = code
  activeDiagramTitle.value = title || 'Diagrama de Arquitectura'
  isDiagramModalOpen.value = true
}

const closeDiagramModal = () => {
  isDiagramModalOpen.value = false
}

const openCodeModal = (code: string, language?: string, extension?: string, title?: string) => {
  activeCode.value = code
  activeCodeLanguage.value = language || 'code'
  activeCodeExtension.value = extension || getLanguageExtension(language)
  activeCodeTitle.value = title || 'Visualizador de Código'
  isCodeModalOpen.value = true
}

const closeCodeModal = () => {
  isCodeModalOpen.value = false
}

const openImageModal = (imageUrl: string, alt?: string, title?: string) => {
  activeImageUrl.value = imageUrl
  activeImageAlt.value = alt || 'Recurso visual'
  activeImageTitle.value = title || 'Visualizador de Imagen'
  isImageModalOpen.value = true
}

const closeImageModal = () => {
  isImageModalOpen.value = false
}

const copyChatCode = async (code: string, blockIndex: number) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedCodeIndex.value = blockIndex
    setTimeout(() => {
      if (copiedCodeIndex.value === blockIndex) {
        copiedCodeIndex.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy code snippet:', err)
  }
}

const downloadChatCode = (code: string, extension?: string, title?: string) => {
  try {
    const ext = extension || 'txt'
    const safeTitle = (title || 'codigo')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '_')
      .slice(0, 30)
    const filename = `${safeTitle}_${Date.now()}.${ext}`
    const mimeType = getMimeTypeForExtension(ext)
    const blob = new Blob([code], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Failed to download chat code:', err)
  }
}

const downloadChatImage = (imageUrl: string, title?: string) => {
  try {
    const safeTitle = (title || 'recurso_visual')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '_')
      .slice(0, 30)
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = `${safeTitle}_${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch (err) {
    console.error('Failed to download chat image:', err)
  }
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

const getInitialSelectedAgents = (): string[] => {
  if (store.selectedAgent && !store.selectedAgents?.includes(store.selectedAgent)) {
    return [store.selectedAgent]
  }
  if (Array.isArray(store.selectedAgents) && store.selectedAgents.length > 0) {
    return [...store.selectedAgents]
  }
  return [store.selectedAgent || 'supervisor']
}

const selectedAgents = ref<string[]>(getInitialSelectedAgents())

watch(() => store.selectedAgent, (newAgent) => {
  if (newAgent && (selectedAgents.value.length <= 1 || !selectedAgents.value.includes(newAgent))) {
    selectedAgents.value = [newAgent]
  }
})

watch(() => store.selectedAgents, (newAgents) => {
  if (Array.isArray(newAgents) && newAgents.length > 0) {
    selectedAgents.value = [...newAgents]
  }
}, { deep: true })

const selectedFiles = ref<File[]>([])
const isAgentDropdownOpen = ref(false)
const agentDropdownRef = ref<HTMLElement | null>(null)

const selectedAgentLabel = computed(() => {
  const count = selectedAgents.value.length
  if (count === 0) return 'Seleccionar agente'
  if (count === 1) {
    const role = selectedAgents.value[0]
    return agentsList.value.find(a => a.value === role)?.label || 'Atenea'
  }
  if (count === agentsList.value.length) {
    return `Todos los agentes (${count})`
  }
  if (count === 2) {
    const l1 = agentsList.value.find(a => a.value === selectedAgents.value[0])?.label || ''
    const l2 = agentsList.value.find(a => a.value === selectedAgents.value[1])?.label || ''
    return `${l1}, ${l2}`
  }
  return `${count} agentes seleccionados`
})

const toggleAgentDropdown = () => {
  if (props.isDebating) return
  isAgentDropdownOpen.value = !isAgentDropdownOpen.value
}

const toggleAgent = (role: string) => {
  const index = selectedAgents.value.indexOf(role)
  if (index >= 0) {
    selectedAgents.value.splice(index, 1)
    if (selectedAgents.value.length === 0) {
      selectedAgents.value = ['supervisor']
    }
  } else if (selectedAgents.value.length === 1 && selectedAgents.value[0] === 'supervisor' && role !== 'supervisor') {
    // If only supervisor was selected and user clicks another agent, select that agent
    selectedAgents.value = [role]
  } else {
    selectedAgents.value.push(role)
  }
  store.selectedAgents = [...selectedAgents.value]
  store.selectedAgent = selectedAgents.value[0] || 'supervisor'
}

const selectAllAgents = () => {
  if (selectedAgents.value.length === agentsList.value.length) {
    selectedAgents.value = ['supervisor']
  } else {
    selectedAgents.value = agentsList.value.map(a => a.value)
  }
  store.selectedAgents = [...selectedAgents.value]
  store.selectedAgent = selectedAgents.value[0] || 'supervisor'
}

const handleClickOutsideAgent = (event: MouseEvent) => {
  if (!agentDropdownRef.value || !isAgentDropdownOpen.value) return
  const path = event.composedPath()
  if (!path.includes(agentDropdownRef.value)) {
    isAgentDropdownOpen.value = false
  }
}

// Cancel debate & info popover state
const showCancelInfo = ref(false)
const cancelInfoRef = ref<HTMLElement | null>(null)

const toggleCancelInfo = () => {
  showCancelInfo.value = !showCancelInfo.value
}

const handleCancelDebate = () => {
  store.cancelDebate()
  showCancelInfo.value = false
}

const handleClickOutsideCancelInfo = (event: MouseEvent) => {
  if (!cancelInfoRef.value || !showCancelInfo.value) return
  const path = event.composedPath()
  if (!path.includes(cancelInfoRef.value)) {
    showCancelInfo.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutsideAgent)
  document.addEventListener('click', handleClickOutsideCancelInfo)
  document.addEventListener('click', closePresentationDownloadMenu)
  window.addEventListener('resize', updateChatScrollState)
  if (typeof store.onTtsChunkReady === 'function') {
    store.onTtsChunkReady((chunk: string, role?: string) => {
      queueTtsSentence(chunk, role)
    })
  }
  if (typeof store.onTtsStop === 'function') {
    store.onTtsStop(() => {
      clearTtsQueues()
    })
  }
  nextTick(() => {
    updateChatScrollState()
    if (typeof ResizeObserver !== 'undefined' && chatScroll.value) {
      scrollResizeObserver = new ResizeObserver(() => {
        updateChatScrollState()
      })
      scrollResizeObserver.observe(chatScroll.value)
      if (chatScroll.value.firstElementChild) {
        scrollResizeObserver.observe(chatScroll.value.firstElementChild)
      }
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideAgent)
  document.removeEventListener('click', handleClickOutsideCancelInfo)
  document.removeEventListener('click', closePresentationDownloadMenu)
  window.removeEventListener('resize', updateChatScrollState)
  scrollResizeObserver?.disconnect()
})

// TTS Queue logic for gapless sentence-by-sentence playback with per-agent role tracking
interface TtsTextItem {
  id: string
  text: string
  role: string
  sessionId: number
}

interface TtsAudioItem {
  id: string
  audio: ArrayBuffer
  role: string
  sessionId: number
}

let ttsSessionId = 0
let prefetchAbortController: AbortController | null = null
let ttsTextQueue: TtsTextItem[] = []
let ttsAudioQueue: TtsAudioItem[] = []
let isPrefetching = false
let isPlayingAudio = false

const clearTtsQueues = () => {
  ttsSessionId++
  if (prefetchAbortController) {
    try {
      prefetchAbortController.abort()
    } catch {}
    prefetchAbortController = null
  }
  ttsTextQueue = []
  ttsAudioQueue = []
  isPrefetching = false
  isPlayingAudio = false
}

// Watch store.isTtsPlaying to abort playback immediately
watch(() => store.isTtsPlaying, (isPlaying) => {
  if (!isPlaying) {
    clearTtsQueues()
  }
}, { flush: 'sync' })

const queueTtsSentence = (sentence: string, role?: string) => {
  if (!store.isVoiceOutputEnabled || !sentence) return
  const clean = cleanTextForTts(sentence)
  if (!clean) return

  const targetRole = role || store.activeTtsRole || 'supervisor'
  store.isTtsPlaying = true
  if (!store.activeTtsRole) {
    store.activeTtsRole = targetRole
  }
  if (typeof store.addReadingAgentRole === 'function') {
    store.addReadingAgentRole(targetRole)
  }

  const chunks = splitTextIntoTtsChunks(clean)
  const currentSession = ttsSessionId
  chunks.forEach(chunk => {
    ttsTextQueue.push({
      id: crypto.randomUUID(),
      text: chunk,
      role: targetRole,
      sessionId: currentSession
    })
  })

  if (!isPrefetching) {
    prefetchTtsQueue().catch(err => {
      console.error('Error prefetching TTS queue:', err)
    })
  }
}

const playVoiceResponse = (text: string, role?: string) => {
  if (!store.isVoiceOutputEnabled || !text) return

  // Clean text from diagrams and markdown for natural voice synthesis
  const cleanText = cleanTextForTts(text)
  if (!cleanText) return

  const targetRole = role || store.activeTtsRole || 'supervisor'
  store.isTtsPlaying = true
  if (!store.activeTtsRole) {
    store.activeTtsRole = targetRole
  }
  if (typeof store.addReadingAgentRole === 'function') {
    store.addReadingAgentRole(targetRole)
  }

  // Split by punctuation (., ?, !, \n, ,, ;, :) for immediate low-latency Time-To-First-Audio
  const sentences = splitTextIntoTtsChunks(cleanText)
  const currentSession = ttsSessionId
  sentences.forEach(sentence => {
    ttsTextQueue.push({
      id: crypto.randomUUID(),
      text: sentence,
      role: targetRole,
      sessionId: currentSession
    })
  })

  if (!isPrefetching) {
    prefetchTtsQueue().catch(err => {
      console.error('Error prefetching TTS queue:', err)
    })
  }
}

const isTtsSessionActive = (session: number) => {
  return session === ttsSessionId && store.isTtsPlaying
}

const handlePrefetchAudioResult = (
  audioBuffer: ArrayBuffer,
  item: TtsTextItem,
  currentSession: number
) => {
  if (!isTtsSessionActive(currentSession)) return
  ttsAudioQueue.push({
    id: item.id,
    audio: audioBuffer,
    role: item.role,
    sessionId: currentSession
  })
  if (store.isTtsPlaying && !isPlayingAudio && currentSession === ttsSessionId) {
    playNextAudio().catch(err => {
      console.error("Error starting audio playback:", err)
    })
  }
}

const prefetchTtsQueue = async () => {
  if (ttsTextQueue.length === 0) {
    isPrefetching = false
    return
  }

  const currentSession = ttsSessionId
  isPrefetching = true
  const item = ttsTextQueue.shift()!

  try {
    prefetchAbortController = new AbortController()
    const response = await fetch('/api/audio/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: item.text, add_silence: false }),
      signal: prefetchAbortController.signal
    })

    if (isTtsSessionActive(currentSession) && response.ok) {
      const audioBuffer = await response.arrayBuffer()
      handlePrefetchAudioResult(audioBuffer, item, currentSession)
    }
  } catch (e: unknown) {
    const isAbort = Boolean(e && typeof e === 'object' && 'name' in e && e.name === 'AbortError')
    if (!isAbort) {
      console.error("Error synthesizing speech:", e)
    }
  } finally {
    const hasMore = isTtsSessionActive(currentSession) && ttsTextQueue.length > 0
    if (hasMore) {
      prefetchTtsQueue().catch(err => {
        console.error("Error prefetching next sentence:", err)
      })
    } else if (currentSession === ttsSessionId) {
      isPrefetching = false
    }
  }
}

const finalizeAgentReadingIfDone = (role: string, currentSession: number) => {
  const stillHasAudio = ttsAudioQueue.some(a => a.role === role && a.sessionId === currentSession)
  const stillHasText = ttsTextQueue.some(t => t.role === role && t.sessionId === currentSession)
  if (!stillHasAudio && !stillHasText) {
    store.removeReadingAgentRole?.(role)
  }
}

const playNextAudio = async () => {
  if (isPlayingAudio) return

  if (ttsAudioQueue.length === 0) {
    if (ttsTextQueue.length === 0 && !isPrefetching) {
      store.stopTts()
    }
    return
  }

  if (!store.isTtsPlaying) return

  const currentSession = ttsSessionId
  isPlayingAudio = true
  const currentItem = ttsAudioQueue.shift()!

  if (currentItem.sessionId !== currentSession) {
    isPlayingAudio = false
    return
  }

  store.activeTtsRole = currentItem.role

  try {
    await store.playTtsAudioChunk?.(currentItem.audio)
  } catch (e) {
    console.error("Play error:", e)
  } finally {
    isPlayingAudio = false
  }

  if (currentSession !== ttsSessionId) return

  finalizeAgentReadingIfDone(currentItem.role, currentSession)

  if (isTtsSessionActive(currentSession)) {
    playNextAudio().catch(err => {
      console.error("Error playing next audio chunk:", err)
    })
  }
}

watch(() => props.messages.length, (newLen, oldLen) => {
  if (newLen > oldLen) {
    const startIndex = Math.max(0, oldLen)
    for (let i = startIndex; i < newLen; i++) {
      const msg = props.messages[i]
      if (msg?.role === 'assistant' && !store.streamingMessageId && !msg.isStreaming) {
        // Determine the agent role for TTS voice synthesis (from agentRole or agentName)
        const match = /^\[(.*?)\]\s/.exec(msg.content)
        const role = msg.agentRole || msg.agentName || (match ? match[1] : undefined) || 'supervisor'
        playVoiceResponse(msg.content, role)
      }
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
  clearTtsQueues()
  store.stopTts()
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  store.submitHitlDecision('approve', '', targets)
  selectedTargetAgents.value = []
}

const handleHitlDivert = () => {
  clearTtsQueues()
  store.stopTts()
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  if (targets.length === 0) {
    alert('Por favor selecciona al menos un agente en los chips para desviar la tarea.')
    return
  }
  store.submitHitlDecision('divert', store.draftMessage.trim(), targets)
  store.draftMessage = ''
  selectedTargetAgents.value = []
}

const hasErrorRecovery = computed(() => {
  const lastHitlEvent = store.rawEvents?.slice().reverse().find(e => e.type === 'hitl_required')
  if (lastHitlEvent?.metadata?.error_recovery === 'true') {
    return true
  }
  return store.agents?.some(a => a.state === 'ERROR') || false
})

const handleHitlRetry = () => {
  clearTtsQueues()
  store.stopTts()
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  store.submitHitlDecision('retry', '', targets)
  selectedTargetAgents.value = []
}

const handleHitlConsolidate = () => {
  clearTtsQueues()
  store.stopTts()
  store.submitHitlDecision('consolidate')
  selectedTargetAgents.value = []
}

const handleHitlFinish = () => {
  clearTtsQueues()
  store.stopTts()
  store.submitHitlDecision('finish')
  selectedTargetAgents.value = []
}

const handleHitlReject = () => {
  clearTtsQueues()
  store.stopTts()
  const targets = store.hitlTargetAgents?.length ? store.hitlTargetAgents : selectedTargetAgents.value
  store.submitHitlDecision('reject', '', targets)
  selectedTargetAgents.value = []
}

const focusRefineInput = async () => {
  clearTtsQueues()
  store.stopTts()
  await nextTick()
  chatInputRef.value?.focus()
}

const onSubmit = async () => {
  if (store.isHitlRequired) {
    clearTtsQueues()
    store.stopTts()
    if (!store.draftMessage.trim()) {
      await focusRefineInput()
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

  const targetForDebate = selectedAgents.value.length > 1 
    ? selectedAgents.value 
    : (selectedAgents.value[0] || 'supervisor')
  store.startDebate(store.draftMessage, targetForDebate, attachmentParam)
  
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

// Auto-scroll to the start of the last message and update scroll state
watch(() => props.messages.length, async (newLen) => {
  await nextTick()
  updateChatScrollState()
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

watch(() => props.isDebating, async () => {
  await nextTick()
  updateChatScrollState()
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
    <div class="p-3.5 md:px-4 md:py-5 border-b border-space-800/50 relative">
      <div class="flex justify-between items-center gap-2">
        <div class="min-w-0 flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full bg-neon-cyan glow-cyan shrink-0"></div>
          <h2 class="font-bold text-white text-xs md:text-[13px] tracking-wider font-mono">CONVERSACIÓN</h2>
        </div>
        <div class="flex items-center space-x-1.5 md:space-x-2 shrink-0">
          <!-- Learn Button -->
          <button 
            @click="handleLearnSession"
            :disabled="store.isLearningSession || messages.length === 0 || props.isDebating"
            class="text-[9px] border border-cyan-800/80 hover:border-neon-cyan text-neon-cyan font-mono px-2.5 md:px-3 h-7 rounded transition-all uppercase tracking-widest bg-[#040e1a] hover:bg-neon-cyan/15 inline-flex items-center justify-center gap-1.5 leading-none disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_10px_rgba(0,229,255,0.08)] cursor-pointer"
            title="Pedir a Metis que sintetice y aprenda la sesión en Obsidian Vault"
            data-test="learn-session-btn"
          >
            <Brain class="w-3.5 h-3.5 shrink-0" :class="{ 'animate-pulse': store.isLearningSession }" />
            <span class="leading-none">{{ store.isLearningSession ? 'Asimilando...' : 'Aprender' }}</span>
          </button>

          <!-- Clear Chat -->
          <button 
            @click="clearChat"
            class="text-[9px] border border-space-700 hover:border-space-500 text-space-400 hover:text-slate-300 font-mono px-2.5 md:px-3 h-7 rounded transition-colors uppercase tracking-widest bg-space-900 inline-flex items-center justify-center leading-none cursor-pointer"
          >
            <span class="leading-none">Limpiar</span>
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
    <div 
      ref="chatScroll" 
      @scroll.passive="updateChatScrollState"
      class="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar p-3.5 md:px-4 md:py-5 space-y-6 min-w-0 max-w-full"
    >
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
              <span class="text-[11px] font-bold text-white tracking-widest font-mono">{{ store.projectName }}</span>
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
              <template v-for="(block, blockIdx) in parseMessageContent(msg.content, { isDocumentAgent: agentHasDocumentViewer(msg.agentName) })" :key="blockIdx">
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
                  <!-- Card Header with Actions (Icon - Diagrama - Botones) -->
                  <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
                    <div class="flex items-center gap-2">
                      <Network class="w-3.5 h-3.5 text-neon-cyan" />
                      <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">Diagrama</span>
                    </div>

                    <div class="flex items-center gap-2">
                      <!-- Copy Button -->
                      <button
                        type="button"
                        @click="copyChatDiagramCode(block.content, i * 100 + blockIdx)"
                        data-test="chat-diagram-copy-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        :title="copiedDiagramIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                        :aria-label="copiedDiagramIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                      >
                        <Check v-if="copiedDiagramIndex === (i * 100 + blockIdx)" class="w-3.5 h-3.5 text-emerald-400" />
                        <Copy v-else class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          {{ copiedDiagramIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar' }}
                        </span>
                      </button>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openDiagramModal(block.content, `Diagrama de ${msg.agentName || 'Arquitectura'}`)"
                        data-test="chat-diagram-view-btn"
                        class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
                        title="Ver diagrama"
                        aria-label="Ver diagrama"
                      >
                        <Eye class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Ver
                        </span>
                      </button>
                    </div>
                  </div>

                  <!-- Code snippet preview -->
                  <pre class="p-3.5 bg-[#020408] font-mono text-xs text-cyan-200/90 overflow-x-auto custom-scrollbar max-h-48 border-t border-space-900/50"><code>{{ block.content }}</code></pre>
                </div>

                <!-- Code Block Card (Dédalo / Fidias / Development) -->
                <div 
                  v-else-if="block.type === 'code'"
                  data-test="chat-code-card"
                  class="my-2 bg-[#050a14] border border-cyan-500/30 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.08)]"
                >
                  <!-- Card Header with Actions (Icon - Código - Botones) -->
                  <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
                    <div class="flex items-center gap-2">
                      <Code2 class="w-3.5 h-3.5 text-neon-cyan" />
                      <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">Código</span>
                    </div>

                    <div class="flex items-center gap-2">
                      <!-- Copy Button -->
                      <button
                        type="button"
                        @click="copyChatCode(block.content, i * 100 + blockIdx)"
                        data-test="chat-code-copy-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        :title="copiedCodeIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                        :aria-label="copiedCodeIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                      >
                        <Check v-if="copiedCodeIndex === (i * 100 + blockIdx)" class="w-3.5 h-3.5 text-emerald-400" />
                        <Copy v-else class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          {{ copiedCodeIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar' }}
                        </span>
                      </button>

                      <!-- Download Button -->
                      <button
                        type="button"
                        @click="downloadChatCode(block.content, block.extension, `codigo_${msg.agentName || 'desarrollo'}`)"
                        data-test="chat-code-download-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        title="Descargar archivo"
                        aria-label="Descargar archivo"
                      >
                        <Download class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Descargar
                        </span>
                      </button>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openCodeModal(block.content, block.language, block.extension, `Código de ${msg.agentName || 'Desarrollo'}`)"
                        data-test="chat-code-view-btn"
                        class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
                        title="Abrir en pantalla completa"
                        aria-label="Abrir en pantalla completa"
                      >
                        <Eye class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Ver
                        </span>
                      </button>
                    </div>
                  </div>

                  <!-- Code snippet preview -->
                  <pre class="p-3.5 bg-[#020408] font-mono text-xs text-cyan-100 overflow-x-auto custom-scrollbar max-h-48 border-t border-space-900/50"><code>{{ block.content }}</code></pre>
                </div>

                <!-- Image Card (Fidias / Visual Resources / Mockups) -->
                <div 
                  v-else-if="block.type === 'image'"
                  data-test="chat-image-card"
                  class="my-2 bg-[#050a14] border border-pink-500/30 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(236,72,153,0.1)]"
                >
                  <!-- Card Header with Actions (Icon - Imágenes - Botones) -->
                  <div class="flex items-center justify-between px-3.5 py-2 bg-[#120818] border-b border-pink-500/30">
                    <div class="flex items-center gap-2">
                      <ImageIcon class="w-3.5 h-3.5 text-pink-400" />
                      <span class="text-xs font-mono font-bold text-pink-400 uppercase tracking-wider select-none">Imágenes</span>
                    </div>

                    <div class="flex items-center gap-2">
                      <!-- Download Button -->
                      <button
                        type="button"
                        @click="downloadChatImage(block.content, block.alt || 'recurso')"
                        data-test="chat-image-download-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        title="Descargar imagen"
                        aria-label="Descargar imagen"
                      >
                        <Download class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Descargar
                        </span>
                      </button>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openImageModal(block.content, block.alt, `Recurso de ${msg.agentName || 'Diseño'}`)"
                        data-test="chat-image-view-btn"
                        class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 shadow-[0_0_10px_rgba(236,72,153,0.2)] transition-all cursor-pointer flex items-center justify-center"
                        title="Ver en pantalla completa"
                        aria-label="Ver en pantalla completa"
                      >
                        <Eye class="w-3.5 h-3.5" />
                        <!-- Hover Tooltip -->
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Ver
                        </span>
                      </button>
                    </div>
                  </div>

                  <!-- Image preview -->
                  <div class="p-3 bg-[#020408] flex items-center justify-center border-t border-space-900/50">
                    <button
                      type="button"
                      class="p-0 bg-transparent border-0 cursor-pointer rounded overflow-hidden focus:outline-none focus:ring-2 focus:ring-pink-500 max-h-60 flex items-center justify-center"
                      :aria-label="`Ver imagen: ${block.alt || 'Recurso visual'}`"
                      @click="openImageModal(block.content, block.alt, `Recurso de ${msg.agentName || 'Diseño'}`)"
                    >
                      <img
                        :src="block.content"
                        :alt="block.alt"
                        data-test="chat-image-preview"
                        class="max-h-60 rounded object-contain hover:opacity-95 transition-opacity"
                      />
                    </button>
                  </div>
                </div>

                <!-- Document Card (Calíope / Technical Documentation) -->
                <div 
                  v-else-if="block.type === 'document'"
                  data-test="chat-document-card"
                  class="my-2 bg-[#050a14] border border-pink-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(236,72,153,0.12)]"
                >
                  <!-- Card Header with Actions (Icon - Documento - Botones) -->
                  <div class="flex items-center justify-between px-3.5 py-2 bg-[#0e0816] border-b border-pink-500/30">
                    <div class="flex items-center gap-2 min-w-0">
                      <FileText class="w-3.5 h-3.5 text-pink-400 shrink-0" />
                      <span class="text-xs font-mono font-bold text-pink-400 uppercase tracking-wider select-none">Documento</span>
                    </div>

                    <div class="flex items-center gap-1.5 shrink-0">
                      <!-- Copy Button -->
                      <button
                        type="button"
                        @click="copyDocContent(block.content, i * 100 + blockIdx)"
                        data-test="chat-doc-copy-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        :title="copiedDocIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar Markdown al portapapeles'"
                        :aria-label="copiedDocIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar Markdown al portapapeles'"
                      >
                        <Check v-if="copiedDocIndex === (i * 100 + blockIdx)" class="w-3.5 h-3.5 text-emerald-400" />
                        <Copy v-else class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          {{ copiedDocIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar' }}
                        </span>
                      </button>

                      <!-- Download .md Button -->
                      <button
                        type="button"
                        @click="downloadMarkdownFile(block.content, block.title || 'documento')"
                        data-test="chat-doc-download-md-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        title="Descargar archivo Markdown (.md)"
                        aria-label="Descargar archivo Markdown (.md)"
                      >
                        <Download class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Descargar .md
                        </span>
                      </button>

                      <!-- Export PDF Button -->
                      <button
                        type="button"
                        @click="exportDocumentToPdf(block.content, block.title || 'documento')"
                        data-test="chat-doc-export-pdf-btn"
                        class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center"
                        title="Descargar / Imprimir en PDF"
                        aria-label="Descargar / Imprimir en PDF"
                      >
                        <Printer class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Descargar .pdf
                        </span>
                      </button>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openDocumentModal(block.content, block.title || 'Documento Técnico')"
                        data-test="chat-doc-view-btn"
                        class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 shadow-[0_0_10px_rgba(236,72,153,0.2)] transition-all cursor-pointer flex items-center justify-center"
                        title="Ver Documento en pantalla completa"
                        aria-label="Ver Documento en pantalla completa"
                      >
                        <Eye class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Ver
                        </span>
                      </button>
                    </div>
                  </div>

                  <!-- Document preview with internal scrollbar -->
                  <div class="p-4 bg-[#02050a] text-slate-200 text-xs leading-relaxed max-h-56 overflow-y-auto custom-scrollbar border-t border-space-900/50 selection:bg-pink-500/30">
                    <div class="doc-body font-sans max-w-none" v-html="renderMarkdownToHtml(block.content)"></div>
                  </div>
                </div>

                <!-- Presentation Block Card (Calíope / Presentation Deck) -->
                <div 
                  v-else-if="block.type === 'presentation'"
                  data-test="chat-presentation-card"
                  class="my-2 bg-[#050a14] border border-cyan-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.12)]"
                >
                  <!-- Card Header with Actions (Icon - Presentación - Botones) -->
                  <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
                    <div class="flex items-center gap-2 min-w-0">
                      <MonitorPlay class="w-3.5 h-3.5 text-neon-cyan shrink-0" />
                      <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">Presentación</span>
                    </div>

                    <div class="flex items-center gap-1.5 shrink-0">
                      <!-- Copy Button -->
                      <button
                        type="button"
                        @click="copyPresentationContent(block.content, i * 100 + blockIdx)"
                        data-test="chat-presentation-copy-btn"
                        class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-cyan-400 text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
                        :title="copiedPresentationIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                        :aria-label="copiedPresentationIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar al portapapeles'"
                      >
                        <Check v-if="copiedPresentationIndex === (i * 100 + blockIdx)" class="w-3.5 h-3.5 text-emerald-400" />
                        <Copy v-else class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          {{ copiedPresentationIndex === (i * 100 + blockIdx) ? 'Copiado' : 'Copiar' }}
                        </span>
                      </button>

                      <!-- Single Download Button with Format Dropdown -->
                      <div class="relative">
                        <button
                          type="button"
                          @click.stop="togglePresentationDownloadMenu(i * 100 + blockIdx)"
                          data-test="chat-presentation-download-btn"
                          class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-cyan-400 text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center gap-1"
                          title="Descargar presentación"
                          aria-label="Descargar presentación"
                          :aria-expanded="activePresentationDownloadMenu === (i * 100 + blockIdx)"
                        >
                          <Download class="w-3.5 h-3.5" />
                          <ChevronDown class="w-2.5 h-2.5 opacity-70 transition-transform duration-150" :class="activePresentationDownloadMenu === (i * 100 + blockIdx) ? 'rotate-180' : ''" />
                          <span
                            v-if="activePresentationDownloadMenu !== (i * 100 + blockIdx)"
                            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                          >
                            Descargar
                          </span>
                        </button>

                        <!-- Download Options Dropdown -->
                        <div
                          v-if="activePresentationDownloadMenu === (i * 100 + blockIdx)"
                          data-test="chat-presentation-download-dropdown"
                          class="absolute right-0 top-full mt-1.5 w-48 bg-[#050b18]/95 border border-cyan-500/40 rounded-xl p-1 shadow-[0_0_20px_rgba(0,229,255,0.25)] backdrop-blur-md z-50 flex flex-col gap-0.5 font-mono text-left animate-in fade-in duration-100"
                        >
                          <button
                            type="button"
                            @click="downloadChatPresentationPptx(block.content, block.title)"
                            data-test="chat-presentation-download-pptx-btn"
                            class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
                          >
                            <MonitorPlay class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                            <span>PowerPoint (.pptx)</span>
                          </button>
                          <button
                            type="button"
                            @click="downloadChatPresentation(block.content, block.title)"
                            data-test="chat-presentation-download-html-btn"
                            class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
                          >
                            <Globe class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                            <span>Web (.html)</span>
                          </button>
                          <button
                            type="button"
                            @click="downloadChatPresentationMarkdown(block.content, block.title)"
                            data-test="chat-presentation-download-md-btn"
                            class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
                          >
                            <FileCode class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                            <span>Markdown (.md)</span>
                          </button>
                        </div>
                      </div>

                      <!-- Open Modal Button -->
                      <button
                        type="button"
                        @click="openPresentationModal(block.content, block.title || `Presentación de ${msg.agentName || 'Atenea'}`)"
                        data-test="chat-presentation-view-btn"
                        class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
                        title="Ver Presentación de Diapositivas"
                        aria-label="Ver Presentación de Diapositivas"
                      >
                        <Eye class="w-3.5 h-3.5" />
                        <span
                          class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                        >
                          Ver
                        </span>
                      </button>
                    </div>
                  </div>

                  <!-- Presentation preview with slide count and cover title -->
                  <div class="p-4 bg-[#02050a] flex items-center justify-between gap-4 border-t border-space-900/50">
                    <div class="min-w-0">
                      <div class="text-xs font-mono font-bold text-white uppercase truncate">
                        {{ block.title || 'Presentación de Diapositivas' }}
                      </div>
                      <div class="text-[11px] font-mono text-cyan-400/80 mt-0.5">
                        {{ block.slideCount ? `${block.slideCount} diapositivas listas para proyectar` : 'Diapositivas interactivas 16:9' }}
                      </div>
                    </div>
                    <button
                      type="button"
                      @click="openPresentationModal(block.content, block.title)"
                      data-test="chat-presentation-project-btn"
                      class="px-3 py-1.5 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
                    >
                      <MonitorPlay class="w-3.5 h-3.5" />
                      <span>Proyectar</span>
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>
      
      <!-- Typing indicator -->
      <div v-if="isDebating" class="flex flex-col items-start max-w-[90%] relative" data-test="typing-indicator">
        <div class="flex items-center space-x-2 mb-2">
          <div class="w-5 h-5 rounded-full border border-neon-green/50 flex items-center justify-center bg-neon-green/10 text-neon-green">
            <Bot class="w-3 h-3" />
          </div>
          <span class="text-[11px] font-bold text-white tracking-widest font-mono">{{ store.projectName }}</span>

          <!-- Cancel Button -->
          <button
            type="button"
            @click="handleCancelDebate"
            class="px-2 py-0.5 bg-red-950/40 hover:bg-red-900/80 border border-red-500/50 hover:border-red-400 text-red-300 hover:text-white text-[9px] font-mono uppercase tracking-widest rounded shadow-sm flex items-center space-x-1.5 transition-all cursor-pointer active:scale-95"
            title="Cancelar deliberación del agente en curso"
            data-test="cancel-debate-btn"
          >
            <Square class="w-2.5 h-2.5 fill-red-400 text-red-400" />
            <span>Cancelar</span>
          </button>

          <!-- Toggle Informativo -->
          <div ref="cancelInfoRef" class="relative inline-flex items-center">
            <button
              type="button"
              @click.stop="toggleCancelInfo"
              class="p-0.5 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer rounded hover:bg-space-800/60"
              :class="{ 'text-cyan-300 bg-space-800': showCancelInfo }"
              title="Información sobre la cancelación"
              data-test="cancel-info-toggle-btn"
            >
              <Info class="w-3.5 h-3.5" />
            </button>

            <!-- Popover informativo -->
            <div
              v-if="showCancelInfo"
              class="absolute left-6 top-0 z-50 w-64 p-2.5 bg-space-900 border border-cyan-500/40 rounded-lg shadow-[0_4px_20px_rgba(0,0,0,0.5)] text-slate-300 text-[11px] font-sans leading-normal animate-fade-in"
              data-test="cancel-info-popover"
            >
              <div class="flex items-start justify-between gap-1 mb-1">
                <span class="font-mono text-[10px] text-cyan-300 font-bold uppercase tracking-wider">Cancelar agente</span>
                <button
                  type="button"
                  @click.stop="showCancelInfo = false"
                  class="text-space-400 hover:text-white p-0.5 rounded cursor-pointer"
                  data-test="cancel-info-close-btn"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
              <p class="text-slate-300 text-[10px]">
                Cancela la ejecución de los agentes en curso inmediatamente si la respuesta se demora o deseas reformular tu consulta sin tener que recargar la página (F5).
              </p>
            </div>
          </div>
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
    <div class="p-4 border-t border-space-800 bg-[#060a11] shrink-0 md:min-h-[162px] flex flex-col justify-center">
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
          <button
            type="button"
            @click="handleHitlRetry"
            data-test="hitl-retry-btn"
            class="p-1.5 rounded-lg border transition-all flex items-center justify-center cursor-pointer group"
            :class="hasErrorRecovery 
              ? 'bg-amber-500/20 hover:bg-amber-500/35 border-amber-400 text-amber-300 ring-2 ring-amber-400/30 animate-pulse' 
              : 'bg-space-800/60 hover:bg-space-700/80 border-space-700/80 text-slate-400 hover:text-amber-400 hover:border-amber-500/40'"
            title="Reintentar ejecución de fase"
            aria-label="Reintentar ejecución de fase"
          >
            <RotateCcw class="w-3.5 h-3.5 transition-transform group-hover:-rotate-90" />
          </button>
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

        <!-- Quick Action Buttons (2 Rows of 3: Row 1 = Aceptar, Consolidar, Finalizar | Row 2 = Refinar, Desviar, Rechazar) -->
        <div class="flex flex-col gap-1.5 pt-1 w-full">
          <!-- Row 1: Aceptar, Consolidar y Finalizar -->
          <div class="grid grid-cols-3 gap-1.5 w-full">
            <button
              type="button"
              @click="handleHitlApprove"
              data-test="hitl-approve-btn"
              class="h-8.5 w-full bg-emerald-500/15 hover:bg-emerald-500/30 border border-emerald-500/60 text-emerald-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Aceptar dictamen y continuar"
            >
              <Check class="w-3.5 h-3.5 shrink-0" />
              <span>Aceptar</span>
            </button>
            <button
              type="button"
              @click="handleHitlConsolidate"
              data-test="hitl-consolidate-btn"
              class="h-8.5 w-full bg-purple-500/15 hover:bg-purple-500/30 border border-purple-500/60 text-purple-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Concluir el debate anticipadamente y consolidar dictamen final con Atenea"
            >
              <Sparkles class="w-3.5 h-3.5 shrink-0" />
              <span>Consolidar</span>
            </button>
            <button
              type="button"
              @click="handleHitlFinish"
              data-test="hitl-finish-btn"
              class="h-8.5 w-full bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/60 text-rose-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Parar y finalizar el debate inmediatamente sin consolidar"
            >
              <Square class="w-3.5 h-3.5 shrink-0" />
              <span>Finalizar</span>
            </button>
          </div>

          <!-- Row 2: Refinar, Desviar y Rechazar -->
          <div class="grid grid-cols-3 gap-1.5 w-full">
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
            <button
              type="button"
              @click="handleHitlReject"
              data-test="hitl-reject-btn"
              class="h-8.5 w-full bg-red-500/15 hover:bg-red-500/30 border border-red-500/60 text-red-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
              title="Rechazar propuesta y reiniciar deliberación"
            >
              <X class="w-3.5 h-3.5 shrink-0" />
              <span>Rechazar</span>
            </button>
          </div>
        </div>
      </div>

      <form @submit.prevent="onSubmit" class="flex flex-col gap-2.5 md:gap-3 relative">
        <div class="flex items-center justify-between gap-2">
          <!-- Left side: Custom Multi-Agent Dropdown Selector & File Upload -->
          <div class="flex items-center gap-2">
            <!-- Custom Multi-Agent Dropdown Selector -->
            <div class="relative" ref="agentDropdownRef">
              <button 
                type="button"
                @click="toggleAgentDropdown"
                :disabled="isDebating && !store.isHitlRequired"
                data-test="agent-dropdown-btn"
                class="flex items-center justify-between min-w-[140px] max-w-[210px] min-h-[36px] md:min-h-0 bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 rounded px-3 py-1.5 text-[11px] font-mono text-cyan-50 shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] transition-all disabled:opacity-50"
              >
                <span class="truncate">{{ selectedAgentLabel }}</span>
                <ChevronDown class="w-3 h-3 text-neon-cyan ml-2 shrink-0 transition-transform" :class="{ 'rotate-180': isAgentDropdownOpen }" />
              </button>
              
              <div 
                v-if="isAgentDropdownOpen"
                class="absolute bottom-full left-0 mb-2 w-56 bg-space-950 border border-neon-cyan/50 rounded shadow-[0_0_15px_rgba(0,229,255,0.15)] overflow-hidden z-50 font-mono text-xs"
              >
                <div class="px-3 py-1.5 bg-space-900 text-neon-cyan/70 text-[9px] uppercase tracking-wider border-b border-neon-cyan/30 flex items-center justify-between">
                  <span>Agentes ({{ selectedAgents.length }})</span>
                  <button
                    type="button"
                    @click.stop="selectAllAgents"
                    class="text-[9px] text-neon-cyan hover:underline uppercase tracking-wider cursor-pointer"
                  >
                    {{ selectedAgents.length === agentsList.length ? 'Solo Atenea' : 'Todos' }}
                  </button>
                </div>
                <div class="max-h-[220px] overflow-y-auto custom-scrollbar">
                  <button 
                    v-for="agent in agentsList" 
                    :key="agent.value"
                    type="button"
                    @click.stop="toggleAgent(agent.value)"
                    data-test="agent-option"
                    :data-selected="selectedAgents.includes(agent.value)"
                    class="w-full text-left px-3 py-2 transition-colors flex items-center justify-between cursor-pointer"
                    :class="selectedAgents.includes(agent.value) ? 'bg-neon-cyan/10 text-neon-cyan' : 'text-slate-300 hover:bg-space-800 hover:text-cyan-200'"
                  >
                    <span class="flex items-center space-x-2 min-w-0">
                      <span 
                        class="w-3.5 h-3.5 rounded-sm border flex items-center justify-center shrink-0 transition-colors"
                        :class="selectedAgents.includes(agent.value) ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan' : 'border-slate-700 bg-space-900'"
                      >
                        <Check v-if="selectedAgents.includes(agent.value)" class="w-2.5 h-2.5 stroke-[3]" />
                      </span>
                      <span 
                        class="w-1.5 h-1.5 rounded-full shrink-0" 
                        :style="agent.colorHex ? { backgroundColor: agent.colorHex } : {}"
                      ></span>
                      <span class="font-bold text-[10px] md:text-[11px] truncate">{{ agent.label }}</span>
                    </span>
                    <span v-if="selectedAgents.includes(agent.value)" class="w-1.5 h-1.5 rounded-full bg-neon-cyan glow-cyan shrink-0 ml-1"></span>
                  </button>
                </div>
              </div>
            </div>

            <label 
              v-if="selectedAgents.includes('learning')" 
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

          <!-- Right side: Scroll Top / Bottom Toggle Button -->
          <button
            v-if="isChatScrollable"
            type="button"
            @click="handleScrollToggle"
            data-test="chat-scroll-toggle-btn"
            class="relative group flex items-center justify-center min-h-[36px] min-w-[36px] md:min-h-0 md:h-[28px] md:w-[28px] bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 text-cyan-300 hover:text-white rounded shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] hover:shadow-[0_0_12px_rgba(0,229,255,0.3)] transition-all cursor-pointer shrink-0"
            :title="scrollDirection === 'down' ? 'Bajar al final del chat' : 'Subir al inicio del chat'"
            :aria-label="scrollDirection === 'down' ? 'Bajar al final del chat' : 'Subir al inicio del chat'"
          >
            <ArrowDown v-if="scrollDirection === 'down'" class="w-3.5 h-3.5" />
            <ArrowUp v-else class="w-3.5 h-3.5" />
            <!-- Hover Tooltip -->
            <span
              class="pointer-events-none absolute bottom-full mb-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
            >
              {{ scrollDirection === 'down' ? 'Bajar al final' : 'Subir al inicio' }}
            </span>
          </button>
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
              class="w-full bg-[#030509] border rounded-xl pl-3.5 md:pl-4 pr-12 py-3 text-base sm:text-sm text-slate-200 focus:outline-none transition-all placeholder:text-[11px] placeholder-space-600 font-mono shadow-inner resize-none custom-scrollbar min-h-[76px] sm:min-h-[88px]"
              :class="store.isHitlRequired ? 'border-neon-amber/60 focus:border-neon-amber focus:ring-1 focus:ring-neon-amber/50' : 'border-space-700 focus:border-neon-cyan'"
              :disabled="isDebating && !store.isHitlRequired"
              @keydown.enter.prevent="onSubmit"
            ></textarea>
            
            <button 
              type="submit"
              data-test="chat-send-btn"
              :disabled="!store.draftMessage.trim() || (isDebating && !store.isHitlRequired)"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 p-2 min-w-[36px] min-h-[36px] flex items-center justify-center bg-[#00e5ff] text-[#060a11] hover:bg-cyan-400 disabled:opacity-50 disabled:hover:bg-[#00e5ff] transition-all rounded-lg shadow-[0_0_10px_rgba(0,229,255,0.3)] cursor-pointer"
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

    <!-- Code Modal Visualizer (Dédalo / Fidias) -->
    <CodeModal
      :is-open="isCodeModalOpen"
      :code="activeCode"
      :language="activeCodeLanguage"
      :extension="activeCodeExtension"
      :title="activeCodeTitle"
      @close="closeCodeModal"
    />

    <!-- Image Modal Visualizer (Fidias) -->
    <ImageModal
      :is-open="isImageModalOpen"
      :image-url="activeImageUrl"
      :alt="activeImageAlt"
      :title="activeImageTitle"
      @close="closeImageModal"
    />

    <!-- Document Modal Visualizer (Calíope) -->
    <DocumentModal
      :is-open="isDocumentModalOpen"
      :content="activeDocContent"
      :title="activeDocTitle"
      @close="closeDocumentModal"
    />

    <!-- Presentation Modal Visualizer (Calíope) -->
    <PresentationModal
      :is-open="isPresentationModalOpen"
      :content="activePresentationContent"
      :title="activePresentationTitle"
      @close="closePresentationModal"
    />
  </div>
</template>
