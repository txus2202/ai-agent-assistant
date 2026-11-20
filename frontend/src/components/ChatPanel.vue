<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useChatArtifacts } from '../composables/useChatArtifacts'
import { useChatAttachments } from '../composables/useChatAttachments'
import { useTtsPlaybackQueue } from '../composables/useTtsPlaybackQueue'
import { useDebateStore, type ChatMessage } from '../stores/debate'
import ChatComposer from './chat/ChatComposer.vue'
import ChatHitlCard from './chat/ChatHitlCard.vue'
import ChatLearningBar from './chat/ChatLearningBar.vue'
import ChatMessageList from './chat/ChatMessageList.vue'
import type {
  ArtifactCopyPayload,
  ArtifactDownloadPayload,
  ArtifactOpenPayload,
  SelectableAgentOption,
} from './chat/types'
import CodeModal from './tools/CodeModal.vue'
import DiagramModal from './tools/DiagramModal.vue'
import DocumentModal from './tools/DocumentModal.vue'
import ImageModal from './tools/ImageModal.vue'
import PresentationModal from './tools/PresentationModal.vue'

const props = defineProps<{
  messages: ChatMessage[]
  isDebating: boolean
}>()

defineEmits<{
  (e: 'toggle-mic'): void
}>()

const store = useDebateStore()
const messageListRef = ref<InstanceType<typeof ChatMessageList> | null>(null)
const composerRef = ref<InstanceType<typeof ChatComposer> | null>(null)
const isChatScrollable = ref(false)
const scrollDirection = ref<'up' | 'down'>('up')

const handleScrollStateChange = (payload: { isScrollable: boolean; direction: 'up' | 'down' }) => {
  isChatScrollable.value = payload.isScrollable
  scrollDirection.value = payload.direction
}

const {
  availableDomains,
  selectedDomain,
  selectedFiles,
  loadDomains,
  handleFileChange,
  removeFile,
  clearFiles,
  uploadSelectedFiles,
} = useChatAttachments()

const artifacts = useChatArtifacts({
  getMessages: () => props.messages,
  getAgents: () => store.agents,
  normalizeAgentRole: store.normalizeAgentRole,
})

const handleArtifactCopy = (payload: ArtifactCopyPayload) => {
  switch (payload.kind) {
    case 'diagram':
      void artifacts.copyChatDiagramCode(payload.content, payload.cardKey)
      break
    case 'code':
      void artifacts.copyChatCode(payload.content, payload.cardKey)
      break
    case 'document':
      void artifacts.copyDocContent(payload.content, payload.cardKey)
      break
    case 'presentation':
      void artifacts.copyPresentationContent(payload.content, payload.cardKey)
      break
  }
}

const handleArtifactOpen = (payload: ArtifactOpenPayload) => {
  switch (payload.kind) {
    case 'diagram':
      artifacts.openDiagramModal(payload.code, payload.title)
      break
    case 'code':
      artifacts.openCodeModal(payload.code, payload.language, payload.extension, payload.title)
      break
    case 'image':
      artifacts.openImageModal(payload.imageUrl, payload.alt, payload.title)
      break
    case 'document':
      artifacts.openDocumentModal(payload.content, payload.title)
      break
    case 'presentation':
      artifacts.openPresentationModal(payload.content, payload.title)
      break
  }
}

const handleArtifactDownload = (payload: ArtifactDownloadPayload) => {
  switch (payload.kind) {
    case 'code':
      artifacts.downloadChatCode(payload.code, payload.extension, payload.title)
      break
    case 'image':
      artifacts.downloadChatImage(payload.imageUrl, payload.title)
      break
    case 'document-md':
      artifacts.downloadChatDocMarkdown(payload.content, payload.title)
      break
    case 'document-pdf':
      artifacts.exportChatDocPdf(payload.content, payload.title)
      break
    case 'presentation-pptx':
      void artifacts.downloadChatPresentationPptx(payload.content, payload.title)
      break
    case 'presentation-html':
      artifacts.downloadChatPresentation(payload.content, payload.title)
      break
    case 'presentation-md':
      artifacts.downloadChatPresentationMarkdown(payload.content, payload.title)
      break
  }
}

const agentsList = computed<SelectableAgentOption[]>(() =>
  (store.agents || []).map((a) => ({
    value: a.role,
    label: a.name,
    colorHex: a.color_hex,
  })),
)

const selectedAgents = computed<string[]>({
  get: () => {
    const storeList = Array.isArray(store.selectedAgents) ? store.selectedAgents : []
    if (store.selectedAgent && (storeList.length <= 1 || !storeList.includes(store.selectedAgent))) {
      return [store.selectedAgent]
    }
    if (storeList.length > 0) {
      return storeList
    }
    return [store.selectedAgent || 'supervisor']
  },
  set: (next: string[]) => {
    const normalized = next.length > 0 ? [...next] : ['supervisor']
    store.selectedAgents = normalized
    store.selectedAgent = normalized[0] || 'supervisor'
  },
})

const { clearTtsQueues, queueTtsSentence, playVoiceResponse } = useTtsPlaybackQueue(store)

watch(
  () => props.messages.length,
  (newLen, oldLen) => {
    if (newLen > oldLen) {
      const startIndex = Math.max(0, oldLen)
      for (let i = startIndex; i < newLen; i++) {
        const msg = props.messages[i]
        if (msg?.role === 'assistant' && !store.streamingMessageId && !msg.isStreaming) {
          const match = /^\[(.*?)\]\s/.exec(msg.content)
          const role =
            msg.agentRole || msg.agentName || (match ? match[1] : undefined) || 'supervisor'
          playVoiceResponse(msg.content, role)
        }
      }
    }
  },
)

let unsubscribeTtsChunk: (() => void) | null = null
let unsubscribeTtsStop: (() => void) | null = null

onMounted(() => {
  void loadDomains()
  document.addEventListener('click', artifacts.closePresentationDownloadMenu)
  if (typeof store.onTtsChunkReady === 'function') {
    const unsub = store.onTtsChunkReady((chunk: string, role?: string) => {
      queueTtsSentence(chunk, role)
    })
    unsubscribeTtsChunk = typeof unsub === 'function' ? unsub : null
  }
  if (typeof store.onTtsStop === 'function') {
    const unsub = store.onTtsStop(() => {
      clearTtsQueues()
    })
    unsubscribeTtsStop = typeof unsub === 'function' ? unsub : null
  }
})

onUnmounted(() => {
  document.removeEventListener('click', artifacts.closePresentationDownloadMenu)
  unsubscribeTtsChunk?.()
  unsubscribeTtsChunk = null
  unsubscribeTtsStop?.()
  unsubscribeTtsStop = null
})

// HITL state and actions
const selectedTargetAgents = ref<string[]>([])

const selectableAgents = computed(() =>
  (store.agents || []).map((a) => ({
    value: a.role,
    label: a.name,
    colorHex: a.color_hex || '#00e5ff',
  })),
)

watch(
  () => store.hitlTargetAgents,
  (newVal) => {
    if (newVal) {
      selectedTargetAgents.value = [...newVal]
    }
  },
  { deep: true, immediate: true },
)

const effectiveSelectedTargets = computed(() =>
  store.hitlTargetAgents && store.hitlTargetAgents.length > 0
    ? store.hitlTargetAgents
    : selectedTargetAgents.value,
)

const hasErrorRecovery = computed(() => {
  const lastHitlEvent = store.rawEvents
    ?.slice()
    .reverse()
    .find((e) => e.type === 'hitl_required')
  if (lastHitlEvent?.metadata?.error_recovery === 'true') {
    return true
  }
  return store.agents?.some((a) => a.state === 'ERROR') || false
})

const toggleTargetAgent = (role: string) => {
  if (typeof store.toggleHitlTargetAgent === 'function') {
    store.toggleHitlTargetAgent(role)
  }
  if (selectedTargetAgents.value.includes(role)) {
    selectedTargetAgents.value = selectedTargetAgents.value.filter((r) => r !== role)
  } else {
    selectedTargetAgents.value.push(role)
  }
}

const stopSpeechAndClearQueues = () => {
  clearTtsQueues()
  store.stopTts()
}

const handleHitlApprove = () => {
  stopSpeechAndClearQueues()
  store.submitHitlDecision('approve', '', effectiveSelectedTargets.value)
  selectedTargetAgents.value = []
}

const handleHitlDivert = () => {
  stopSpeechAndClearQueues()
  const targets = effectiveSelectedTargets.value
  if (targets.length === 0) {
    alert('Por favor selecciona al menos un agente en los chips para desviar la tarea.')
    return
  }
  store.submitHitlDecision('divert', store.draftMessage.trim(), targets)
  store.draftMessage = ''
  selectedTargetAgents.value = []
}

const handleHitlRetry = () => {
  stopSpeechAndClearQueues()
  store.submitHitlDecision('retry', '', effectiveSelectedTargets.value)
  selectedTargetAgents.value = []
}

const handleHitlConsolidate = () => {
  stopSpeechAndClearQueues()
  store.submitHitlDecision('consolidate')
  selectedTargetAgents.value = []
}

const handleHitlFinish = () => {
  stopSpeechAndClearQueues()
  store.submitHitlDecision('finish')
  selectedTargetAgents.value = []
}

const handleHitlReject = () => {
  stopSpeechAndClearQueues()
  store.submitHitlDecision('reject', '', effectiveSelectedTargets.value)
  selectedTargetAgents.value = []
}

const focusRefineInput = async () => {
  stopSpeechAndClearQueues()
  await nextTick()
  composerRef.value?.focusInput()
}

const onSubmit = async () => {
  if (store.isHitlRequired) {
    stopSpeechAndClearQueues()
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

  let attachmentParam: string | string[] | null = null
  try {
    attachmentParam = await uploadSelectedFiles((file) => store.uploadFile(file))
  } catch (e) {
    console.error('Failed to upload file:', e)
    alert('Error uploading file. Please try again.')
    return
  }

  const targetForDebate =
    selectedAgents.value.length > 1
      ? selectedAgents.value
      : selectedAgents.value[0] || 'supervisor'
  if (selectedDomain.value) {
    store.startDebate(store.draftMessage, targetForDebate, attachmentParam, selectedDomain.value)
  } else {
    store.startDebate(store.draftMessage, targetForDebate, attachmentParam)
  }

  store.draftMessage = ''
  clearFiles()
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

const setActiveTab = (_tab: 'chat' | 'observability') => {
  // Observability is located in the right column alongside AgentTopology
}

defineExpose({
  onSubmit,
  setActiveTab,
})
</script>

<template>
  <div class="flex flex-col h-full bg-[#060a11] border-r border-space-800 font-sans">
    <ChatLearningBar
      :is-learning-session="store.isLearningSession"
      :can-learn="messages.length > 0 && !props.isDebating"
      :learning-status-message="store.learningStatusMessage"
      :selected-files="selectedFiles"
      @learn-session="handleLearnSession"
      @clear-chat="clearChat"
      @dismiss-learning-status="store.learningStatusMessage = null"
      @clear-files="clearFiles"
      @remove-file="removeFile"
    />

    <ChatMessageList
      ref="messageListRef"
      :messages="messages"
      :memoized-message-blocks="artifacts.memoizedMessageBlocks.value"
      :is-debating="isDebating"
      :is-tts-playing="store.isTtsPlaying"
      :project-name="store.projectName"
      :copied-diagram-index="artifacts.copiedDiagramIndex.value"
      :copied-code-index="artifacts.copiedCodeIndex.value"
      :copied-doc-index="artifacts.copiedDocIndex.value"
      :copied-presentation-index="artifacts.copiedPresentationIndex.value"
      :active-presentation-download-menu="artifacts.activePresentationDownloadMenu.value"
      @stop-tts="store.stopTts()"
      @cancel-debate="store.cancelDebate()"
      @scroll-state-change="handleScrollStateChange"
      @copy="handleArtifactCopy"
      @open="handleArtifactOpen"
      @download="handleArtifactDownload"
      @toggle-presentation-download="artifacts.togglePresentationDownloadMenu"
    />

    <div class="p-4 border-t border-space-800 bg-[#060a11] shrink-0 md:min-h-[162px] flex flex-col justify-center">
      <ChatHitlCard
        v-if="store.isHitlRequired"
        :selectable-agents="selectableAgents"
        :selected-targets="effectiveSelectedTargets"
        :has-error-recovery="hasErrorRecovery"
        @toggle-target="toggleTargetAgent"
        @retry="handleHitlRetry"
        @approve="handleHitlApprove"
        @consolidate="handleHitlConsolidate"
        @finish="handleHitlFinish"
        @refine="focusRefineInput"
        @divert="handleHitlDivert"
        @reject="handleHitlReject"
      />

      <ChatComposer
        ref="composerRef"
        v-model:draft-message="store.draftMessage"
        v-model:selected-agents="selectedAgents"
        v-model:selected-domain="selectedDomain"
        :agents-list="agentsList"
        :available-domains="availableDomains"
        :selected-files-count="selectedFiles.length"
        :is-hitl-required="store.isHitlRequired"
        :is-debating="isDebating"
        :is-chat-scrollable="isChatScrollable"
        :scroll-direction="scrollDirection"
        @files-selected="handleFileChange"
        @scroll-toggle="messageListRef?.toggleScroll()"
        @submit="onSubmit"
      />
    </div>

    <DiagramModal
      :is-open="artifacts.isDiagramModalOpen.value"
      :code="artifacts.activeDiagramCode.value"
      :title="artifacts.activeDiagramTitle.value"
      @close="artifacts.closeDiagramModal"
    />

    <CodeModal
      :is-open="artifacts.isCodeModalOpen.value"
      :code="artifacts.activeCode.value"
      :language="artifacts.activeCodeLanguage.value"
      :extension="artifacts.activeCodeExtension.value"
      :title="artifacts.activeCodeTitle.value"
      @close="artifacts.closeCodeModal"
    />

    <ImageModal
      :is-open="artifacts.isImageModalOpen.value"
      :image-url="artifacts.activeImageUrl.value"
      :alt="artifacts.activeImageAlt.value"
      :title="artifacts.activeImageTitle.value"
      @close="artifacts.closeImageModal"
    />

    <DocumentModal
      :is-open="artifacts.isDocumentModalOpen.value"
      :content="artifacts.activeDocContent.value"
      :title="artifacts.activeDocTitle.value"
      @close="artifacts.closeDocumentModal"
    />

    <PresentationModal
      :is-open="artifacts.isPresentationModalOpen.value"
      :content="artifacts.activePresentationContent.value"
      :title="artifacts.activePresentationTitle.value"
      @close="artifacts.closePresentationModal"
    />
  </div>
</template>
