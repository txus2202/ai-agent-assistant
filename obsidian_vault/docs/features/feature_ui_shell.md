---
created: 2026-09-17
updated: 2026-09-17
type: spec
phase: 4
layer: presentation
status: implemented
tags: [ui, layout, vue, dashboard, sci-fi, design-system, atenea]
category: meta-project
---

# Feature: UI Shell & Design System

**As a** user
**I want** a stunning sci-fi mission control interface
**So that** ATENEA feels like a living, breathing AI system, not just a chatbot.

## Visual Identity

The UI follows the **"Sci-Fi Agent Observability Core"** aesthetic from the Stitch prototype:
- Deep space dark backgrounds with subtle grid lines
- Neon cyan / emerald / red color-coding per agent state
- 3D particle orb in the center — the visual heartbeat of the system
- Monospace font for all system data; Inter sans-serif for content
- Glow effects on active elements; blur + transparency for panels

## Design Tokens (Tailwind custom config)

```js
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        space: {
          950: '#05070c',
          900: '#070b12',
          850: '#0b111c',
          800: '#0f1726',
          750: '#141f33',
          700: '#1a2942',
        },
        neon: {
          green:      '#00ff9d',
          cyan:       '#00e5ff',
          blue:       '#2979ff',
          amber:      '#ffd000',
          red:        '#ff3366',
          purple:     '#b347ff',
          orange:     '#ff8800',
          darkgreen:  '#15803d',
          lightgreen: '#22c55e',
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    }
  }
}
```

## Agent Color Map

Each agent has a color identity used for: orb beam color, card glow, progress bar, status badge.

| Agent | Color | Tailwind class | Hex |
|---|---|---|---|
| NL Interpreter | Cyan | `text-cyan-300 border-cyan-500` | `#00e5ff` |
| Innovator Architect | Light Green | `text-lime-400 border-lime-500` | `#22c55e` |
| Senior Architect | Dark Green | `text-emerald-400 border-emerald-600` | `#00ff9d` |
| The Judge | Red | `text-rose-400 border-rose-500` | `#ef4444` |
| Diagrammer | Purple | `text-purple-400 border-purple-500` | `#b347ff` |
| DevOps & SecOps | Orange | `text-orange-400 border-orange-500` | `#ff8800` |

## Global Layout (3-Column)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HEADER — A.T.E.N.E.A. branding, status badge, icon controls            │
├────────────────┬────────────────────────────────┬───────────────────────┤
│  LEFT PANEL    │     CENTER — PARTICLE ORB       │   RIGHT PANEL         │
│  (≈370px)      │     (flex-1, full height)       │   (≈370px)            │
│                │                                 │                       │
│  Tab: OBSERV.  │  ┌──────────────────────────┐  │  Agent Topology       │
│  Tab: CHAT IA  │  │   3D Orb Canvas          │  │  6 Agent Cards        │
│                │  │   (color shifts per       │  │                       │
│  System Health │  │    active agent)          │  │  Orchestration Card   │
│  Agent Latency │  └──────────────────────────┘  │  HITL Action Button   │
│  Event Log     │  Status bar + orb stats         │                       │
│  ─────────     │                                 │                       │
│  or Chat panel │  Bottom: MIC VOZ + indicators   │                       │
└────────────────┴────────────────────────────────┴───────────────────────┘
```

## Global Custom CSS

```css
/* Cyberpunk grid background */
.bg-grid-telemetry {
  background-size: 32px 32px;
  background-image:
    linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px);
}

/* Glow effects */
.glow-green  { box-shadow: 0 0 15px -2px rgba(0,255,157,0.35), inset 0 0 12px -2px rgba(0,255,157,0.15); }
.glow-cyan   { box-shadow: 0 0 15px -2px rgba(0,229,255,0.35), inset 0 0 12px -2px rgba(0,229,255,0.15); }
.glow-red    { box-shadow: 0 0 15px -2px rgba(255,51,102,0.35), inset 0 0 12px -2px rgba(255,51,102,0.15); }
.glow-purple { box-shadow: 0 0 15px -2px rgba(179,71,255,0.35), inset 0 0 12px -2px rgba(179,71,255,0.15); }
.glow-orange { box-shadow: 0 0 15px -2px rgba(255,136,0,0.35), inset 0 0 12px -2px rgba(255,136,0,0.15); }
.glow-active-white { box-shadow: 0 0 35px rgba(255,255,255,0.8), 0 0 12px rgba(248,250,252,0.6); }

/* Futuristic 4px scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: rgba(11,17,28,0.8); }
::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.25); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,229,255,0.5); }
```

## Component List

| Component | Location | Purpose |
|---|---|---|
| `AppShell.vue` | `layouts/` | 3-column grid + header |
| `AppHeader.vue` | `components/` | Logo, status badge, icon tray |
| `ParticleOrb.vue` | `components/` | Canvas 2D animated sphere (color-reactive) |
| `OrbStatusBar.vue` | `components/` | Stats below orb (flux %, topology) |
| `AgentTopology.vue` | `components/` | Right panel: 6 agent cards + orchestration |
| `AgentCard.vue` | `components/` | Single agent status card with glow |
| `HITLActionButton.vue` | `components/` | Context-aware primary action button |
| `ObservabilityPanel.vue` | `components/` | Left tab: system health, latency, logs |
| `ChatPanel.vue` | `components/` | Left tab: conversation + input |
| `EventLog.vue` | `components/` | Scrolling real-time log stream |
| `VoiceBar.vue` | `components/` | Bottom MIC VOZ + indicators |

## Header Structure

```
[ SYSTEM CORE v4.9.2-STABLE ]  [ ⚙ A.T.E.N.E.A. — subtitle ]  [ ● STATUS ]  [ 🔊 🔔 ⚙ ]
```
- Left: version string (mono, slate-400)
- Center: branding box with top cyan accent line + CPU icon + bold title + subtitle
- Right: system status pill (color changes per debate state) + icon controls

## ParticleOrb.vue

A Canvas 2D component that renders:
1. Ambient floating dust particles
2. 3D rotating sphere of connected particle nodes (constellation network)
3. A colored "beam" emitting from the active agent's sector

**Color states (reactive to `useDebateStore`):**

| Store state | Orb beam color | Particle color |
|---|---|---|
| idle | none | white (`#ffffff`) |
| NL_INTERPRETER active | cyan | white + cyan tinge |
| INNOVATOR active | light green | white + lime |
| SENIOR_ARCHITECT active | dark green | white + emerald |
| THE_JUDGE active | red | white + rose |
| DIAGRAMMER active | purple | white + purple |
| DEVOPS_SECOPS active | orange | white + orange |

The orb is interactive: drag to rotate (mouse/touch).

## Acceptance Criteria

### Scenario 1: Layout is 3-column on xl screens

```
Given viewport width ≥ 1280px
Then left panel, center orb, and right panel are side-by-side
```

### Scenario 2: Layout stacks on small screens

```
Given viewport width < 768px
Then panels stack vertically: top = right (agent topology), center = orb, bottom = left (chat/observ)
```

### Scenario 3: Orb changes color when agent becomes active

```
Given debate starts and NL_INTERPRETER begins
When AGENT_STARTED event received
Then orb beam color transitions to cyan within 300ms
```

### Scenario 4: Header status badge reflects debate state

```
Idle → "SYSTEM IDLE: STANDBY" (cyan, pulse)
Running → "SUPERVISOR ONLINE: DUAL-THREAD" (emerald, pulse)
Judge → "SUPERVISOR: THE JUDGE AUDIT ACTIVE" (red, pulse)
```

## Implementation Notes

- Tailwind CSS via `npm install -D tailwindcss postcss autoprefixer`
- Lucide icons via `lucide-vue-next` package
- ParticleOrb is a pure Canvas 2D component — no Three.js dependency needed (the Stitch prototype implements it in ~200 lines of vanilla JS that we port to a Vue component)
- `Inter` font loaded via Google Fonts in `index.html`
- Global CSS in `src/assets/main.css`
