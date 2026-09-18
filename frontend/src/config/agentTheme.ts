export interface AgentTheme {
  hex: string
  colorClass: string
  glowClass: string
}

export const AGENT_THEME: Record<string, AgentTheme> = {
  // Map backend Enum values to Frontend styles
  'nl_interpreter':      { hex: '#00e5ff', colorClass: 'text-neon-cyan',       glowClass: 'glow-cyan' },
  'innovator_architect': { hex: '#22c55e', colorClass: 'text-neon-lightgreen', glowClass: 'glow-green' },
  'senior_architect':    { hex: '#00ff9d', colorClass: 'text-neon-darkgreen',  glowClass: 'glow-cyan' },
  'the_judge':           { hex: '#ef4444', colorClass: 'text-neon-red',        glowClass: 'glow-red' },
  'diagrammer':          { hex: '#b347ff', colorClass: 'text-neon-purple',     glowClass: 'glow-purple' },
  'devops_secops':       { hex: '#ff8800', colorClass: 'text-neon-orange',     glowClass: 'glow-orange' },
}

// Fallback theme for unknown agents
export const DEFAULT_AGENT_THEME: AgentTheme = { 
  hex: '#ffffff', 
  colorClass: 'text-white', 
  glowClass: 'glow-active-white' 
}
