# Feature: Cosmic Particle Orb (ParticleOrb.vue)

## Overview
The `ParticleOrb.vue` is the central visual component of the ATENEA user interface. It represents the AI agent system's "brain" and current state. 

## Requirements
- Render a 3D spherical projection of particles using HTML5 Canvas.
- Provide a "Standby" (Idle) state when `isDebating` is `false`, displaying a 100% white celestial sphere.
- Provide an "Active" state when `isDebating` is `true`, where particles shift colors to match `activeAgentColor` and rotate faster.
- Include CSS-animated outer rings and glowing elements behind the canvas.
- Incorporate the Audio Waveform Visualizer UI, microphone buttons, and mock "Human-In-The-Loop" controls. These are structurally included now to be wired up later when the Voice Integration (Phase 5) is implemented.

## Component Props
- `isDebating: boolean` - Controls the state of the orb (standby vs active debate).
- `activeAgentColor: string` - Determines the color of the particles and outer glows when debating.

## Future Context
As per the roadmap (Phase 5), the voice integration will utilize the Audio Spectrum Canvas and the microphone buttons embedded inside this component. The UI is mocked right now, but the DOM structure will be fully available for easy integration.

## Testing Strategy
Due to the difficulty of testing the Canvas API within Vitest/JSDOM, tests will focus on:
1. Component mounting and unmounting correctly.
2. The `window.requestAnimationFrame` and `window.cancelAnimationFrame` functions being called appropriately.
3. Prop watchers firing when the `isDebating` or `activeAgentColor` state changes.
4. Ensuring the audio UI elements are present in the DOM for future integration.
