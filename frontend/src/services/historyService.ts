import { httpClient } from './httpClient'
import type { DebateSessionRecord } from './debateApiService'

export type HistoryFilterType = 'all' | 'hitl' | 'today' | 'week'

export interface ListDebatesParams {
  limit: number
  offset: number
  filter: HistoryFilterType
  search?: string
}

export interface HistoryDebateSummary {
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
  events?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export interface PaginatedDebatesResponse {
  total: number
  total_all?: number
  limit: number
  offset: number
  items: HistoryDebateSummary[]
}

export const historyService = {
  listDebates(params: ListDebatesParams): Promise<HistoryDebateSummary[] | PaginatedDebatesResponse> {
    const queryParams = new URLSearchParams({
      limit: String(params.limit),
      offset: String(params.offset),
      filter: params.filter,
    })
    const query = params.search?.trim()
    if (query) {
      queryParams.set('search', query)
    }
    return httpClient.get<HistoryDebateSummary[] | PaginatedDebatesResponse>(
      `/api/debates?${queryParams.toString()}`,
    )
  },

  getDebate(id: string): Promise<DebateSessionRecord> {
    return httpClient.get<DebateSessionRecord>(`/api/debates/${encodeURIComponent(id)}`)
  },

  deleteDebate(id: string): Promise<unknown> {
    return httpClient.delete<unknown>(`/api/debates/${encodeURIComponent(id)}`)
  },
}

