import { defineStore } from 'pinia'
import {
  configService,
  type AgentConfig,
  type ProviderConfig,
  type UpdateAgentConfigPayload,
} from '../services/configService'

export type { AgentConfig, ModelConfig, ProviderConfig } from '../services/configService'

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
        const { providers, isProbing } = await configService.loadProviders()
        this.providers = providers

        if (isProbing) {
          // Silently refresh model list once background probing completes
          setTimeout(() => {
            void this.loadProviders()
          }, 3500)
        }
      } catch (error) {
        console.error('Failed to load providers:', error)
      }
    },

    async loadAgentsConfig() {
      this.isLoading = true
      try {
        this.agentsConfig = await configService.loadAgentsConfig()
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
        const payload: UpdateAgentConfigPayload = { provider, model_name: modelName }
        if (ragTopK !== undefined) {
          payload.rag_top_k = ragTopK
        }
        if (ragMinScore !== undefined) {
          payload.rag_min_score = ragMinScore
        }

        await configService.updateAgentConfig(role, payload)

        const index = this.agentsConfig.findIndex((a) => a.id === role)
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
      } catch (error) {
        console.error(`Failed to update agent config for ${role}:`, error)
      }
    },
  },
})
