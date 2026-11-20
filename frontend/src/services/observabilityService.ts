import { httpClient } from './httpClient'

export interface ObservabilityStats {
  cpu_percent?: number
  memory_percent?: number
  cluster_status?: string
  langfuse_metrics_enabled?: boolean
  langfuse_dashboard_url?: string
}

export const observabilityService = {
  getStats(): Promise<ObservabilityStats> {
    return httpClient.get<ObservabilityStats>('/api/observability/stats')
  },
}

