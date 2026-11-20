---
created: 2026-10-20
updated: 2026-10-20
type: spec
phase: 5
layer: cross-cutting
status: implemented
category: meta-project
tags: [sdd, agents, display-name, hitl, checkpoints, decoupling]
---

# SDD: Unificación de Identidad por display_name y Checkpoints Dinámicos

## 1. Contexto y Justificación
Actualmente en el sistema coexisten dos formas de identificar a los agentes:
1. **`AgentRole` (Enum con claves en inglés antiguo):** `NL_INTERPRETER`, `INNOVATOR`, `SENIOR_ARCHITECT`, `THE_JUDGE`, etc., cuyos valores de string son `nl_interpreter`, `innovator_architect`, `the_judge`, etc.
2. **`display_name` (Identidad real del agente):** `Hermes`, `Ícaro`, `Hestia`, `Sphinx`, `Aracne`, `Hefesto`, `Metis`, `Atenea`.

Esta duplicidad provoca:
- Disonancia cognitiva y acoplamiento innecesario en `supervisor_agent.py` (referencias como `AgentRole.INNOVATOR`, `AgentRole.THE_JUDGE`).
- Checkpoints estáticos arbitrarios heredados (`1_interpreter`, `2_architects`, `3_judge`).
- Mapeos frágiles en el frontend (`CHECKPOINT_ROLES = { '2_architects': 'innovator_architect' }` y `normalizeAgentRole`).

## 2. Objetivos
1. **Identidad Unificada por `display_name`:**
   - La identidad principal del agente pasa a ser su nombre visible (`display_name`), sin depender de `AgentRole`.
   - `get_profile(name)` busca directamente por `display_name` (insensible a mayúsculas/minúsculas y acentos).
   - Mantener retrocompatibilidad transparente para que llamadas existentes que pasen strings antiguos sigan resolviendo el perfil.
2. **Checkpoints Dinámicos:**
   - Eliminar `1_interpreter`, `2_architects` y `3_judge`.
   - Formatear los checkpoints dinámicamente como `after_{display_name}` (ej. `after_Hermes`, `after_Ícaro`, `after_Sphinx`) o el propio nombre del agente.
   - Enviar en el evento `SupervisorEvent` el agente responsable directo (`metadata={"checkpoint": f"after_{agent.display_name}", "agent": agent.display_name}`).
3. **Limpieza del Orquestador (`supervisor_agent.py`):**
   - Eliminar dependencias de `AgentRole.INNOVATOR`, `AgentRole.THE_JUDGE`, etc.
   - Orquestar pasando perfiles o nombres directos (`"Hermes"`, `["Ícaro", "Hestia"]`, `"Sphinx"`, `["Aracne", "Hefesto"]`).
4. **Simplificación en el Frontend (`debate.ts` y componentes):**
   - Eliminar `CHECKPOINT_ROLES`.
   - `findAgent` busca directamente por `name` (o `id` si coincide).
   - Los mensajes del chat reflejan directamente el nombre real (`[Hermes]`, `[Ícaro]`, `[Atenea]`) en lugar de `[innovator_architect]`.

## 3. Especificación Técnica por Capas

### A. Capa de Dominio (`backend/src/domain/agents/`)
- **`sub_agent_profiles.py`**:
  - `SubAgentProfile`: El campo `display_name` (ej. `"Hermes"`) es la clave canónica de identidad.
  - `get_profile(identifier: str | AgentRole) -> SubAgentProfile`: Busca primero por coincidencia exacta o `lower()` contra `display_name`, y secundariamente contra el rol antiguo si se proporciona.
  - Diccionario canónico indexado por `display_name.lower()` y aliases.
  - Mantener `AgentRole` como clase utilitaria deprecada con propiedades que devuelvan el `display_name` para no romper dependencias externas si las hubiera.
- **`supervisor_events.py`**:
  - `SupervisorEvent.role`: Pasa a ser `str | None`, almacenando directamente el `display_name` del agente (ej. `"Hermes"`, `"Ícaro"`, `"Atenea"`).

### B. Capa de Aplicación (`backend/src/application/agents/`)
- **`sub_agent_runner.py`**:
  - Acepta `agent: str | SubAgentProfile` en lugar de requerir obligatoriamente `AgentRole`.
- **`supervisor_agent.py`**:
  - Reemplazar todas las referencias a `AgentRole.INNOVATOR`, `AgentRole.SENIOR_ARCHITECT`, `AgentRole.THE_JUDGE`, `AgentRole.NL_INTERPRETER`, `AgentRole.DIAGRAMMER`, `AgentRole.DEVOPS_SECOPS` por sus perfiles o nombres directos (`"Hermes"`, `"Ícaro"`, `"Hestia"`, `"Sphinx"`, etc.).
  - Reemplazar checkpoints `1_interpreter` $\rightarrow$ `after_Hermes`, `2_architects` $\rightarrow$ `after_Ícaro`, `3_judge` $\rightarrow$ `after_Sphinx`.

### C. Capa de Presentación e Infraestructura (`backend/src/presentation/` y `infrastructure/`)
- **`serializers.py`**:
  - `event_to_dict`: serializa `role: event.role` (string con el `display_name`).
- **`wake_word_service.py`**:
  - El resultado de detección de wake word devuelve `agent_role: profile.display_name` y `display_name: profile.display_name`.

### D. Capa Frontend (`frontend/src/`)
- **`debate.ts`**:
  - Eliminar tabla estática `CHECKPOINT_ROLES`.
  - `findAgent(identifier)`: compara insensiblemente contra `agent.name` y `agent.id`.
  - `handleHitlRequired`: extrae el agente directamente de `event.metadata?.agent || event.role || checkpoint`.
  - `pushAgentMessage`: formatea `[${agentName}]` directamente.

## 4. Plan de Pruebas (TDD)
1. **Tests de Dominio:** Verificar que `get_profile` resuelve por `display_name` ("Hermes", "hermes", "Ícaro", "icaro", "Sphinx", etc.) y que `SupervisorEvent` acepta strings de nombre.
2. **Tests de Aplicación:** Verificar `SupervisorAgent` con checkpoints dinámicos (`after_Hermes`, `after_Ícaro`, `after_Sphinx`) y ejecución sin referencias a `AgentRole.INNOVATOR`.
3. **Tests de Frontend:** Actualizar tests de `debate.spec.ts` y componentes para validar checkpoints dinámicos y resolución directa por nombre.
