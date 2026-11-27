import { httpClient } from './httpClient'

export interface AgentConfig {
  id: string
  name: string
  description?: string
  color_hex?: string
  provider: string
  model_name: string
  rag_top_k?: number
  rag_min_score?: number
  uses_rag?: boolean
  supports_hitl?: boolean
  can_ingest_documents?: boolean
  topology_roles?: string[]
  tools?: string[]
}

export interface ModelConfig {
  id: string
  name: string
}

export interface ProviderConfig {
  id: string
  name: string
  models: ModelConfig[]
}

export interface EligibleTopologyAgent {
  id: string
  name: string
  description: string
  color_hex: string
  uses_rag?: boolean
  supports_hitl?: boolean
}

export interface TopologySupervisorInfo {
  id: string
  name: string
  description: string
  color_hex: string
}

export interface DebateTopology {
  project_name?: string
  project_description?: string
  supervisor: string
  interpreters: string[]
  proposers: string[]
  reviewers: string[]
  evaluators: string[]
  implementers: string[]
  review_rounds?: number
  is_customized?: boolean
  supervisor_agent?: TopologySupervisorInfo
  eligible_agents?: EligibleTopologyAgent[]
}

export interface UpdateTopologyPayload {
  interpreters: string[]
  proposers: string[]
  reviewers: string[]
  evaluators: string[]
  implementers: string[]
  review_rounds: number
}

export interface ProvidersCatalogResult {
  providers: ProviderConfig[]
  isProbing: boolean
}

export interface UpdateAgentConfigPayload {
  provider: string
  model_name: string
  rag_top_k?: number
  rag_min_score?: number
}

export const configService = {
  async loadProviders(): Promise<ProvidersCatalogResult> {
    const { data, headers } = await httpClient.getWithMeta<ProviderConfig[]>('/api/models')
    const isProbing = headers?.get?.('x-models-probing') === '1'
    const providers = Array.isArray(data)
      ? data.filter((p) => p.models && p.models.length > 0)
      : []
    return { providers, isProbing }
  },

  loadAgentsConfig(): Promise<AgentConfig[]> {
    return httpClient.get<AgentConfig[]>('/api/config/agents')
  },

  updateAgentConfig(role: string, payload: UpdateAgentConfigPayload): Promise<unknown> {
    return httpClient.put<unknown>(`/api/config/agents/${encodeURIComponent(role)}`, payload)
  },

  getTopology(): Promise<DebateTopology> {
    return httpClient.get<DebateTopology>('/api/config/topology')
  },

  updateTopology(payload: UpdateTopologyPayload): Promise<DebateTopology> {
    return httpClient.put<DebateTopology>('/api/config/topology', payload)
  },

  resetTopology(): Promise<DebateTopology> {
    return httpClient.delete<DebateTopology>('/api/config/topology')
  },
}
