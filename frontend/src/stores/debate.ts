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
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/debate'
    
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('[WS] Connected to', wsUrl)
      isConnected.value = true
      reconnectAttempts = 0
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleSupervisorEvent(data)
      } catch (e) {
        console.error('[WS] Failed to parse message', event.data)
      }
    }
    
    ws.onclose = () => {
      console.log('[WS] Disconnected')
      isConnected.value = false
      ws = null
      attemptReconnect()
    }
    
    ws.onerror = (error) => {
      console.error('[WS] Error', error)
      // onclose will be triggered automatically
    }
  }

  function attemptReconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
    }
    
    // Exponential backoff (max 10s)
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000)
    console.log(`[WS] Attempting to reconnect in ${delay}ms...`)
    
    reconnectTimeout = setTimeout(() => {
      reconnectAttempts++
      connect()
    }, delay)
  }

  function startDebate(userRequest: string) {
    if (!isConnected.value || !ws) {
      messages.value.push({ role: 'assistant', content: 'Error: Cannot start debate, disconnected from server. Trying to reconnect...' })
      connect()
      return
    }

    isDebating.value = true
    messages.value.push({ role: 'user', content: userRequest })
    
    ws.send(JSON.stringify({ type: 'start', user_request: userRequest }))
  }

  function handleSupervisorEvent(event: any) {
    if (event.type === 'hitl_required') {
      isHitlRequired.value = true
      hitlCheckpoint.value = event.metadata?.checkpoint || null
      messages.value.push({ role: 'assistant', content: event.content || 'HITL Required' })
    } else if (event.type === 'agent_started') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'ACTIVE'
    } else if (event.type === 'agent_completed') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'COMPLETED'
    } else if (event.type === 'done') {
      isDebating.value = false
      messages.value.push({ role: 'assistant', content: event.content || 'Debate finished.' })
    } else if (event.type === 'error') {
      isDebating.value = false
      messages.value.push({ role: 'assistant', content: `Error: ${event.content}` })
    } else if (event.type === 'message') {
      messages.value.push({ role: 'assistant', content: `[${event.role}] ${event.content}` })
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

  // Connect automatically on store initialization
  connect()

  return {
    isConnected,
    isDebating,
    isHitlRequired,
    hitlCheckpoint,
    messages,
    agents,
    isAgentsLoaded,
    loadAgents,
    connect,
    startDebate,
    handleSupervisorEvent,
    submitHitlDecision,
    get ws() { return ws } // Getter for testing purposes
  }
})
