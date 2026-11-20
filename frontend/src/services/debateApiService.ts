import { httpClient } from './httpClient'

export interface UploadAttachmentResponse {
  ok?: boolean
  attachment_id?: string
  path?: string
}

export interface VaultDomainItem {
  id: string
  name: string
  description?: string
  path?: string
}

export interface LearnSessionPayload {
  session_id: string
  content?: string
}

export interface LearnSessionResponse {
  ok?: boolean
  generated_file?: string
  file?: string
  chunks_ingested?: number
}

export interface DebateSessionRecord {
  id: string
  created_at?: string
  status?: string
  events?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export const debateApiService = {
  async uploadFile(file: File): Promise<string> {
    const formData = new FormData()
    formData.append('file', file)
    const data = await httpClient.postFormData<UploadAttachmentResponse>('/api/upload', formData)
    const ref = data.attachment_id || data.path
    if (!ref) {
      throw new Error('Upload failed')
    }
    return ref
  },

  getDebateSession(sessionId: string): Promise<DebateSessionRecord> {
    return httpClient.get<DebateSessionRecord>(`/api/debates/${encodeURIComponent(sessionId)}`)
  },

  learnSession(payload: LearnSessionPayload): Promise<LearnSessionResponse> {
    return httpClient.post<LearnSessionResponse>('/api/learning/session', payload)
  },

  listLearningDomains(): Promise<VaultDomainItem[]> {
    return httpClient.get<VaultDomainItem[]>('/api/learning/domains')
  },
}

