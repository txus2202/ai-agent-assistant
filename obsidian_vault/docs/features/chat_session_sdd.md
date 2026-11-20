---
created: 2026-10-19
updated: 2026-10-19
type: spec
phase: 5
layer: cross-cutting
status: implemented
category: meta-project
tags: [sdd, chat, session, multi-turn, history, sqlite]
---

# Software Design Document (SDD) - Sesión Continua de Chat Multi-Agente (Multi-turn Chat Session)

## 1. Introducción y Objetivo
Permitir que la conversación con ATENEA y sus subagentes especializados (Sphinx, Hefesto, Hermes, Ícaro, Hestia, Metis, Aracne) se mantenga como una **única sesión continua de diálogo (multi-turn)** mientras el usuario no limpie la ventana de chat o recargue la página (F5).

Cada intervención (dirigida a cualquier agente o al supervisor) debe pertenecer a la misma sesión (`session_id`), preservando el contexto, acumulando las métricas de consumo de tokens y unificando el registro de auditoría en la base de datos SQLite.

---

## 2. Arquitectura de Sesión

### 2.1 Identificador de Sesión (`session_id`)
- **Origen en Frontend:**
  - El store de Pinia (`debate.ts`) mantiene una referencia reactiva `currentSessionId: Ref<string | null>`.
  - Al enviar el primer mensaje en una ventana vacía, si `currentSessionId` es `null`, se genera un UUID v4 (`crypto.randomUUID()`).
  - Cada mensaje subsiguiente enviado por el WebSocket `/ws/debate` incluye `"session_id": currentSessionId.value`.
  - La sesión solo se resetea a `null` cuando:
    1. El usuario pulsa "Limpiar conversación" (`clearSession()`).
    2. Se recarga la aplicación en el navegador (F5).
    3. Se carga una sesión histórica diferente desde `/history` (`loadDebate(debate)` fija `currentSessionId = debate.id`).

### 2.2 Gestión en Backend (`DebateWebSocketHandler`)
- **Reutilización de Registro en SQLite:**
  - Si el payload `start` contiene un `session_id`:
    - Se consulta `debate_repo.find_by_id(session_id)`.
    - Si existe, se reutiliza el mismo `DebateRecord`, actualizando su estado a `"running"`, su `target_agent` y registrando el nuevo turno.
    - Si no existe (primer turno de una nueva sesión), se crea un `DebateRecord` con `id = session_id`.
- **Registro Cronológico de Eventos (`user_message`):**
  - Al recibir cada petición, el backend persiste un evento explícito de tipo `user_message`:
    ```json
    {
      "type": "user_message",
      "role": "user",
      "content": "user_request text...",
      "metadata": { "target_agent": "the_judge" }
    }
    ```
  - Los eventos de respuesta (`agent_started`, `agent_completed`, `done`, `hitl_required`) se anexan cronológicamente a continuación dentro del mismo `events_json` de la sesión.
- **Trazabilidad y Observabilidad:**
  - Cada turno genera un span/traza vinculado al mismo `session_id`, garantizando observabilidad integral de toda la sesión sin fragmentación.

---

## 3. Métricas y Estado de Agentes Acumulativo
- **Tokens y Coste Acumulado:**
  - `sessionTotalTokens` y `sessionCachedTokens` no se resetean a cero en cada mensaje; se acumulan de forma incremental turno tras turno para mostrar el uso real y el ahorro de caché de la sesión completa.
- **Topología de Agentes:**
  - Al iniciar un nuevo turno, los agentes que no intervienen vuelven a `STANDBY`, mientras que el agente del turno activo pasa a `ACTIVE` y finalmente a `COMPLETED`. Las métricas de latencia y tokens se agregan por agente en el store.

---

## 4. Reconstrucción Histórica (`loadDebate`)
Al consultar `/history` y seleccionar una sesión archivada:
- Se muestra como un único hilo conversacional con todos los turnos del usuario y las respuestas de los distintos agentes que participaron.
- Al restaurar la sesión en el chat principal, `loadDebate` lee la secuencia completa de eventos (incluyendo los `user_message`) y repone el diálogo exacto en el panel de chat, restaurando además `currentSessionId = debate.id` para que el usuario pueda continuar chateando en ese mismo hilo.
