import { ref } from 'vue'
import { debateApiService, type VaultDomainItem } from '../services/debateApiService'

export function useChatAttachments() {
  const availableDomains = ref<VaultDomainItem[]>([])
  const selectedDomain = ref<string>('')
  const selectedFiles = ref<File[]>([])

  const loadDomains = async () => {
    try {
      const data = await debateApiService.listLearningDomains()
      if (Array.isArray(data)) {
        availableDomains.value = data
      }
    } catch {
      // Keep empty list when domains endpoint is unavailable
    }
  }

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

  const uploadSelectedFiles = async (
    uploadFn: (file: File) => Promise<string> = (file) => debateApiService.uploadFile(file),
  ): Promise<string | string[] | null> => {
    if (selectedFiles.value.length === 0) {
      return null
    }
    const attachmentUrls = await Promise.all(selectedFiles.value.map((file) => uploadFn(file)))
    if (attachmentUrls.length === 1 && attachmentUrls[0]) {
      return attachmentUrls[0]
    }
    if (attachmentUrls.length > 1) {
      return attachmentUrls
    }
    return null
  }

  return {
    availableDomains,
    selectedDomain,
    selectedFiles,
    loadDomains,
    handleFileChange,
    removeFile,
    clearFiles,
    uploadSelectedFiles,
  }
}

