import { stripAgentHeaderPrefixes } from './ttsFilter'

export type AgentState = 'STANDBY' | 'ACTIVE' | 'COMPLETED' | 'ERROR'
export type HitlDecisionType =
  | 'approve'
  | 'refine'
  | 'divert'
  | 'finish'
  | 'consolidate'
  | 'retry'
  | 'reject'

export interface Agent {
  role: string
  name: string
  description?: string
  color_hex?: string
  state: AgentState
  tokens?: number
  promptTokens?: number
  completionTokens?: number
  latency?: number
  turns?: number
  startedAt?: number
  uses_rag?: boolean
  supports_hitl?: boolean
  can_ingest_documents?: boolean
  topology_roles?: string[]
  tools?: string[]
}

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  agentRole?: string
  agentName?: string
  colorHex?: string
  isStreaming?: boolean
}

export interface SupervisorEvent {
  id?: string
  type: string
  timestamp?: string
  role?: string | null
  content?: string
  metadata?: {
    checkpoint?: string
    latency_seconds?: number | string
    tokens?: number | string
    prompt_tokens?: number | string
    completion_tokens?: number | string
    total_tokens?: number | string
    cached_tokens?: number | string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface DebateSession {
  id?: string
  created_at?: string
  user_request?: string
  status?: string
  events?: SupervisorEvent[]
  [key: string]: unknown
}

export function createStableIdGenerator(): (prefix: string) => string {
  let idFallbackSeq = 0
  return (prefix: string): string => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return `${prefix}_${crypto.randomUUID()}`
    }
    idFallbackSeq += 1
    return `${prefix}_${Date.now()}_${idFallbackSeq}`
  }
}

export function normalizeAgentRole(r?: string | null): string {
  if (!r) return ''
  const lower = r.toLowerCase().replaceAll('-', '_').trim()
  if (lower === 'innovator') return 'innovator_architect'
  if (lower === 'atenea') return 'supervisor'
  return lower
}

/**
 * Strips initial agent/role prefixes like "[nl_interpreter] ", "[the_judge] ",
 * and markdown headers like "## Interpretation\n".
 * Consolidated with utils/ttsFilter.ts.
 */
export function cleanAgentMessageContent(
  rawContent: string,
  knownAgentNames?: Iterable<string>,
): string {
  return stripAgentHeaderPrefixes(rawContent, knownAgentNames)
}

export function resolveHitlUserMessage(
  decision: HitlDecisionType,
  feedback?: string,
  effectiveTargets?: string[],
): string | null {
  if ((decision === 'refine' || decision === 'divert') && feedback?.trim()) {
    return feedback.trim()
  }
  if (decision === 'consolidate') {
    return 'Concluir debate y consolidar dictamen final con Atenea.'
  }
  if (decision === 'finish') {
    return 'Finalizar debate inmediatamente sin consolidación.'
  }
  if (decision === 'retry') {
    return effectiveTargets?.length
      ? `Reintentar ejecución de fase para agentes: ${effectiveTargets.join(', ')}.`
      : 'Reintentar ejecución de la fase.'
  }
  return null
}

export function buildCompletionDedupKey(role: string, event: SupervisorEvent): string {
  const tok = String(event.metadata?.total_tokens || event.metadata?.tokens || '')
  const contentLen = event.content ? String(event.content.length) : '0'
  return `${role}:${tok}:${contentLen}`
}

export function stripFailedBlocksFromHitlContent(rawContent: string): string {
  const trimmed = rawContent.trim()
  if (!trimmed.includes('[Fallo') && !trimmed.includes('[Error')) {
    return trimmed
  }
  const sections = trimmed.split('---').map((s) => s.trim()).filter(Boolean)
  const validSections = sections.filter((s) => {
    const withoutHeader = s.replace(/^##[^\r\n]*\r?\n+/, '').trim()
    return !withoutHeader.startsWith('[Fallo') && !withoutHeader.startsWith('[Error')
  })
  return validSections.join('\n\n---\n\n')
}

export function hasAuthoritativeTokenMetadata(event: SupervisorEvent): boolean {
  return Boolean(
    event.metadata?.tokens ||
      event.metadata?.total_tokens ||
      event.metadata?.prompt_tokens ||
      event.metadata?.completion_tokens,
  )
}

export function applyAgentLatencyFromEvent(agent: Agent, event: SupervisorEvent): void {
  if (event.metadata?.latency_seconds) {
    agent.latency = Number(event.metadata.latency_seconds)
  } else if (agent.startedAt) {
    agent.latency = Number(((Date.now() - agent.startedAt) / 1000).toFixed(2))
  }
}

export function applyAgentTokensFromEvent(agent: Agent, event: SupervisorEvent): number {
  let pTokens = 0
  let cTokens = 0
  if (event.metadata?.prompt_tokens) {
    pTokens = Number.parseInt(String(event.metadata.prompt_tokens), 10) || 0
    if (pTokens > 0) {
      agent.promptTokens = (agent.promptTokens || 0) + pTokens
    }
  }
  if (event.metadata?.completion_tokens) {
    cTokens = Number.parseInt(String(event.metadata.completion_tokens), 10) || 0
    if (cTokens > 0) {
      agent.completionTokens = (agent.completionTokens || 0) + cTokens
    }
  }

  if (event.metadata?.tokens || event.metadata?.total_tokens) {
    const tokens = Number.parseInt(String(event.metadata.total_tokens || event.metadata.tokens), 10)
    agent.tokens = (agent.tokens || 0) + tokens
    if (!pTokens && !cTokens) {
      const estIn = Math.max(15, Math.round(tokens * 0.6))
      const estOut = Math.max(10, tokens - estIn)
      agent.promptTokens = (agent.promptTokens || 0) + estIn
      agent.completionTokens = (agent.completionTokens || 0) + estOut
    } else if (!pTokens && cTokens > 0) {
      const estIn = Math.max(15, Math.round(cTokens * 1.2))
      agent.promptTokens = (agent.promptTokens || 0) + estIn
      agent.tokens = (agent.tokens || 0) + estIn
    }
    return tokens
  }

  if (event.content) {
    const words = event.content.trim().split(/\s+/).filter(Boolean).length
    const outTokens = Math.max(12, Math.round(words * 1.35))
    const inTokens = Math.max(25, Math.round(outTokens * 1.4))
    agent.tokens = (agent.tokens || 0) + outTokens + inTokens
    agent.promptTokens = (agent.promptTokens || 0) + inTokens
    agent.completionTokens = (agent.completionTokens || 0) + outTokens
    return outTokens + inTokens
  }
  return 0
}

