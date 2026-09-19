import { defineStore } from 'pinia'

export interface AgentConfig {
  id: string
  name: string
  provider: string
  model_name: string
}

interface ConfigState {
  agentsConfig: AgentConfig[]
  isLoading: boolean
}

export const useConfigStore = defineStore('config', {
  state: (): ConfigState => ({
    agentsConfig: [],
    isLoading: false,
  }),
  
  actions: {
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
    
    async updateAgentConfig(role: string, provider: string, modelName: string) {
      try {
        const response = await fetch(`/api/config/agents/${role}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ provider, model_name: modelName }),
        })
        
        if (response.ok) {
          const index = this.agentsConfig.findIndex(a => a.id === role)
          if (index !== -1) {
            this.agentsConfig[index].provider = provider
            this.agentsConfig[index].model_name = modelName
          }
        }
      } catch (error) {
        console.error(`Failed to update agent config for ${role}:`, error)
      }
    }
  }
})
