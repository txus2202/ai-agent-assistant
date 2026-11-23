import { computed, ref, type Ref } from 'vue'
import { useTimedReset } from './useTimedReset'
import type { Agent, ChatMessage } from '../utils/debateHelpers'
import {
  downloadMarkdownFile,
  exportDocumentToPdf,
  extractDocumentTitle,
  renderMarkdownToHtml,
} from '../utils/markdownRenderer'
import { getLanguageExtension, parseMessageContent, type MessageBlock } from '../utils/messageParser'
import { getMimeTypeForExtension } from '../utils/mimeHelper'
import { downloadBlobFile, downloadUrlFile, sanitizeFilename } from '../utils/fileDownload'
import {
  downloadPresentationHtml,
  downloadPresentationMarkdown,
  exportPresentationPptx,
} from '../utils/presentationExporter'
import { sanitizeHtml } from '../utils/sanitize'
import { parsePresentation } from '../utils/slideParser'

export interface RenderedMessageBlock extends MessageBlock {
  renderedHtml?: string
}

interface ParsedMessageCacheEntry {
  content: string
  isDocAgent: boolean
  toolsKey: string
  blocks: RenderedMessageBlock[]
}

export interface UseChatArtifactsDeps {
  getMessages: () => ChatMessage[]
  getAgents: () => Agent[] | undefined
  normalizeAgentRole?: (role?: string | null) => string
}

async function copyTextWithReset(
  text: string,
  index: number,
  trigger: (value: number) => void,
  label: string,
) {
  try {
    await navigator.clipboard.writeText(text)
    trigger(index)
  } catch (err) {
    console.error(`Failed to copy ${label}:`, err)
  }
}

export function useChatArtifacts(deps: UseChatArtifactsDeps) {
  const isDiagramModalOpen = ref(false)
  const activeDiagramCode = ref('')
  const activeDiagramTitle = ref('Diagrama')
  const { state: copiedDiagramIndex, trigger: triggerCopiedDiagram } = useTimedReset<number | null>(
    null,
  )

  const isCodeModalOpen = ref(false)
  const activeCode = ref('')
  const activeCodeLanguage = ref('code')
  const activeCodeExtension = ref('')
  const activeCodeTitle = ref('Visualizador de Código')
  const { state: copiedCodeIndex, trigger: triggerCopiedCode } = useTimedReset<number | null>(null)

  const isImageModalOpen = ref(false)
  const activeImageUrl = ref('')
  const activeImageAlt = ref('Recurso visual')
  const activeImageTitle = ref('Visualizador de Imagen')

  const isDocumentModalOpen = ref(false)
  const activeDocContent = ref('')
  const activeDocTitle = ref('Documento Técnico')
  const { state: copiedDocIndex, trigger: triggerCopiedDoc } = useTimedReset<number | null>(null)
  const activeDocumentDownloadMenu: Ref<number | null> = ref(null)

  const isPresentationModalOpen = ref(false)
  const activePresentationContent = ref('')
  const activePresentationTitle = ref('Presentación')
  const { state: copiedPresentationIndex, trigger: triggerCopiedPresentation } =
    useTimedReset<number | null>(null)
  const activePresentationDownloadMenu: Ref<number | null> = ref(null)

  const parsedBlocksCache = new Map<string, ParsedMessageCacheEntry>()

  const resolveAgentForMessage = (agentName?: string): Agent | undefined => {
    if (!agentName) return undefined
    const lower = agentName.toLowerCase()
    const normalize = deps.normalizeAgentRole
    const norm = normalize ? normalize(agentName).toLowerCase() : lower
    return deps.getAgents()?.find(
      (a) =>
        a.name?.toLowerCase() === lower ||
        a.role?.toLowerCase() === lower ||
        (normalize ? normalize(a.role).toLowerCase() === norm : false),
    )
  }

  const getMessageCacheKey = (msg: ChatMessage, index: number): string =>
    msg.id ? `id:${msg.id}` : `idx:${index}`

  const memoizedMessageBlocks = computed<RenderedMessageBlock[][]>(() => {
    const activeKeys = new Set<string>()
    const result = deps.getMessages().map((msg, index) => {
      const key = getMessageCacheKey(msg, index)
      activeKeys.add(key)
      if (msg.role === 'user') return []
      const agent = resolveAgentForMessage(msg.agentName || msg.agentRole)
      const agentTools = agent?.tools ?? []
      const isDocAgent = agentTools.includes('document_viewer')
      const toolsKey = agentTools.join(',')
      const cached = parsedBlocksCache.get(key)
      if (
        cached?.content === msg.content &&
        cached?.isDocAgent === isDocAgent &&
        cached?.toolsKey === toolsKey
      ) {
        return cached.blocks
      }
      const blocks: RenderedMessageBlock[] = parseMessageContent(msg.content, {
        isDocumentAgent: isDocAgent,
        agentTools,
      }).map((block) =>
        block.type === 'document'
          ? { ...block, renderedHtml: sanitizeHtml(renderMarkdownToHtml(block.content)) }
          : block,
      )
      parsedBlocksCache.set(key, { content: msg.content, isDocAgent, toolsKey, blocks })
      return blocks
    })

    for (const cachedKey of parsedBlocksCache.keys()) {
      if (!activeKeys.has(cachedKey)) {
        parsedBlocksCache.delete(cachedKey)
      }
    }
    return result
  })

  const toggleDocumentDownloadMenu = (index: number) => {
    activeDocumentDownloadMenu.value =
      activeDocumentDownloadMenu.value === index ? null : index
  }

  const closeDocumentDownloadMenu = () => {
    activeDocumentDownloadMenu.value = null
  }

  const togglePresentationDownloadMenu = (index: number) => {
    activePresentationDownloadMenu.value =
      activePresentationDownloadMenu.value === index ? null : index
  }

  const closePresentationDownloadMenu = () => {
    activePresentationDownloadMenu.value = null
    activeDocumentDownloadMenu.value = null
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

  const copyChatDiagramCode = (code: string, blockIndex: number) =>
    copyTextWithReset(code, blockIndex, triggerCopiedDiagram, 'diagram code')

  const copyChatCode = (code: string, blockIndex: number) =>
    copyTextWithReset(code, blockIndex, triggerCopiedCode, 'code snippet')

  const copyDocContent = (content: string, index: number) =>
    copyTextWithReset(content, index, triggerCopiedDoc, 'document content')

  const copyPresentationContent = (content: string, index: number) =>
    copyTextWithReset(content, index, triggerCopiedPresentation, 'presentation content')

  const downloadChatCode = (code: string, extension?: string, title?: string) => {
    try {
      const ext = extension || 'txt'
      const safeTitle = sanitizeFilename(title, 'codigo')
      const filename = `${safeTitle}_${Date.now()}.${ext}`
      downloadBlobFile(code, filename, getMimeTypeForExtension(ext))
    } catch (err) {
      console.error('Failed to download chat code:', err)
    }
  }

  const downloadChatImage = (imageUrl: string, title?: string) => {
    try {
      const safeTitle = sanitizeFilename(title, 'recurso_visual')
      downloadUrlFile(imageUrl, `${safeTitle}_${Date.now()}.png`)
    } catch (err) {
      console.error('Failed to download chat image:', err)
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

  const downloadChatDocMarkdown = (content: string, title?: string) => {
    closeDocumentDownloadMenu()
    downloadMarkdownFile(content, title || 'documento')
  }

  const exportChatDocPdf = (content: string, title?: string) => {
    closeDocumentDownloadMenu()
    exportDocumentToPdf(content, title || 'documento')
  }

  return {
    isDiagramModalOpen,
    activeDiagramCode,
    activeDiagramTitle,
    copiedDiagramIndex,
    isCodeModalOpen,
    activeCode,
    activeCodeLanguage,
    activeCodeExtension,
    activeCodeTitle,
    copiedCodeIndex,
    isImageModalOpen,
    activeImageUrl,
    activeImageAlt,
    activeImageTitle,
    isDocumentModalOpen,
    activeDocContent,
    activeDocTitle,
    copiedDocIndex,
    activeDocumentDownloadMenu,
    isPresentationModalOpen,
    activePresentationContent,
    activePresentationTitle,
    copiedPresentationIndex,
    activePresentationDownloadMenu,
    memoizedMessageBlocks,
    toggleDocumentDownloadMenu,
    closeDocumentDownloadMenu,
    togglePresentationDownloadMenu,
    closePresentationDownloadMenu,
    openPresentationModal,
    closePresentationModal,
    openDocumentModal,
    closeDocumentModal,
    openDiagramModal,
    closeDiagramModal,
    openCodeModal,
    closeCodeModal,
    openImageModal,
    closeImageModal,
    copyChatDiagramCode,
    copyChatCode,
    copyDocContent,
    copyPresentationContent,
    downloadChatCode,
    downloadChatImage,
    downloadChatPresentation,
    downloadChatPresentationPptx,
    downloadChatPresentationMarkdown,
    downloadChatDocMarkdown,
    exportChatDocPdf,
  }
}

