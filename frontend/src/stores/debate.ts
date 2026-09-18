import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AgentState = 'STANDBY' | 'ACTIVE' | 'COMPLETED'

export interface Agent {
  role: string
  name: string
  state: AgentState
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export const useDebateStore = defineStore('debate', () => {
  const isConnected = ref(false)
  const isDebating = ref(false)
  const isHitlRequired = ref(false)
  const hitlCheckpoint = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  
  const agents = ref<Agent[]>([])
  const isAgentsLoaded = ref(false)

  // Fetch agent topology from backend
  async function loadAgents() {
    try {
      const response = await fetch('/api/config/agents')
      if (!response.ok) throw new Error('Failed to fetch agents config')
      
      const data: Array<{ id: string, name: string }> = await response.json()
      agents.value = data.map(agent => ({
        role: agent.id,
        name: agent.name,
        state: 'STANDBY'
      }))
      isAgentsLoaded.value = true
    } catch (error) {
      console.error('Error loading agents:', error)
      // Fallback for dev if backend isn't running
      agents.value = [
        { role: 'nl_interpreter', name: 'Nl Interpreter', state: 'STANDBY' },
        { role: 'innovator_architect', name: 'Innovator Architect', state: 'STANDBY' },
        { role: 'senior_architect', name: 'Senior Architect', state: 'STANDBY' },
        { role: 'the_judge', name: 'The Judge', state: 'STANDBY' },
        { role: 'diagrammer', name: 'Diagrammer', state: 'STANDBY' },
        { role: 'devops_secops', name: 'Devops Secops', state: 'STANDBY' }
      ]
      isAgentsLoaded.value = true
    }
  }

  let ws: WebSocket | null = null

  function startDebate(userRequest: string) {
    isDebating.value = true
    messages.value.push({ role: 'user', content: userRequest })
    
    // In a real app, this would initialize ws and send the start message
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'start', user_request: userRequest }))
    }
  }

  function handleSupervisorEvent(event: any) {
    if (event.type === 'hitl_required') {
      isHitlRequired.value = true
      hitlCheckpoint.value = event.metadata?.checkpoint || null
      messages.value.push({ role: 'assistant', content: event.content })
    } else if (event.type === 'agent_started') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'ACTIVE'
    } else if (event.type === 'agent_completed') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'COMPLETED'
    } else if (event.type === 'done') {
      isDebating.value = false
      messages.value.push({ role: 'assistant', content: event.content })
    }
  }

  function submitHitlDecision(decision: 'approve' | 'refine' | 'reject', feedback?: string) {
    isHitlRequired.value = false
    hitlCheckpoint.value = null
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'hitl_response',
        decision,
        feedback: feedback || ''
      }))
    }
  }

  return {
    isConnected,
    isDebating,
    isHitlRequired,
    hitlCheckpoint,
    messages,
    agents,
    isAgentsLoaded,
    loadAgents,
    startDebate,
    handleSupervisorEvent,
    submitHitlDecision,
    ws
  }
})
