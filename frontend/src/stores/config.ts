import { defineStore } from 'pinia'

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

interface ConfigState {
  agentsConfig: AgentConfig[]
  providers: ProviderConfig[]
  isLoading: boolean
}

export const useConfigStore = defineStore('config', {
  state: (): ConfigState => ({
    agentsConfig: [],
    providers: [],
    isLoading: false,
  }),
  
  actions: {
    async loadProviders() {
      try {
        const response = await fetch('/api/models')
        if (response.ok) {
          const data = await response.json()
          this.providers = data.filter((p: ProviderConfig) => p.models && p.models.length > 0)
        }
      } catch (error) {
        console.error('Failed to load providers:', error)
      }
    },

    async loadAgentsConfig() {
      this.isLoading = true
      try {
        const response = await fetch('/api/config/agents')
        if (response.ok) {
          this.agentsConfig = await response.json()
        }
      } catch (error) {
        console.error('Failed to load agents config:', error)
      } finally {
        this.isLoading = false
      }
    },
    
    async updateAgentConfig(
      role: string,
      provider: string,
      modelName: string,
      ragTopK?: number,
      ragMinScore?: number,
    ) {
      try {
        const payload: Record<string, unknown> = { provider, model_name: modelName }
        if (ragTopK !== undefined) {
          payload.rag_top_k = ragTopK
        }
        if (ragMinScore !== undefined) {
          payload.rag_min_score = ragMinScore
        }

        const response = await fetch(`/api/config/agents/${role}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        })
        
        if (response.ok) {
          const index = this.agentsConfig.findIndex(a => a.id === role)
          if (index !== -1) {
            this.agentsConfig[index]!.provider = provider
            this.agentsConfig[index]!.model_name = modelName
            if (ragTopK !== undefined) {
              this.agentsConfig[index]!.rag_top_k = ragTopK
            }
            if (ragMinScore !== undefined) {
              this.agentsConfig[index]!.rag_min_score = ragMinScore
            }
          }
        }
      } catch (error) {
        console.error(`Failed to update agent config for ${role}:`, error)
      }
    }
  }
})
