---
created: 2026-10-20
updated: 2026-10-20
type: spec
phase: 5
layer: application
status: implemented
category: meta-project
tags: [sdd, supervisor, hitl, adaptive-triage, atenea, voice-commands]
---

# Software Design Document (SDD) - Supervisor Adaptativo & Flujo HITL Integrado (Punto 5)

## 1. Introducción y Objetivo

El propósito de esta funcionalidad es evolucionar a **Atenea** de un pipeline secuencial rígido ("todo o nada") a un **sistema multi-agente adaptativo, inteligente y colegiado**, optimizado para ejecutarse de forma eficiente en hardware contenido:

1. **Personalidad y Prompts de Atenea:** Actualizar el perfil y los prompts de Atenea al castellano formal, mitológico y autoritario, acorde a los demás 7 agentes del consejo técnico.
2. **Orquestación y Enrutamiento Inteligente (Adaptive Triage):** Permitir que Atenea clasifique la intención de la petición del usuario para:
   - Responder directamente a consultas o saludos sin movilizar innecesariamente a los 6 agentes.
   - Delegar directamente en un especialista atómico (p. ej. solo diagramas a Aracne, solo despliegue/seguridad a Hefesto, solo aprendizaje a Metis).
   - Saltar fases del debate cuando la información ya está estructurada (p. ej. saltar a Hermes si los requisitos ya son técnicos y precisos, comenzando directamente en los arquitectos Ícaro y Hestia).
   - Ejecutar el debate colegiado completo estándar como fallback o ante problemas de arquitectura complejos.
3. **Checkpoints HITL Dinámicos y Desacoplados:**
   - Eliminar identificadores rígidos (`1_interpreter`, `2_architects`, `3_judge`) en favor de checkpoints contextuales asociados al agente o fase completada (`checkpoint: f"after_{agent_role}"`).
   - Introducir el atributo `supports_hitl: bool = True` en `SubAgentProfile` (en la capa de Dominio).
   - Permitir que el agente o la orquestadora evalúen si es necesario solicitar HITL en función de la existencia de dudas, discrepancias o preguntas bloqueantes.
   - Permitir la **selección de agentes destinatarios (`target_agents`)** en la respuesta de HITL para desviar la aprobación, rechazo o refinamiento a los agentes deseados.
4. **HITL Integrado en el Chat (`ChatPanel.vue`):**
   - Eliminar el control HITL de la barra lateral para centralizar la interacción en el flujo natural del chat.
   - Mostrar una tarjeta interactiva en el chat con botones directos (`[✓ Aceptar]`, `[✗ Rechazar]`, `[✏ Refinar]`) y chips multiselección de agentes destino.
   - Reutilizar el textarea nativo del chat para escribir las instrucciones de refinamiento.
5. **Control de Voz Manos Libres con Vosk:**
   - Reconocimiento en tiempo real de comandos por voz para resolver los checkpoints HITL (`"Aceptar"` / `"Rechazar"` / `"Refinar..."`).

---

## 2. Personalidad y Prompts de Atenea (Dominio & Aplicación)

### 2.1 Perfil de Dominio (`SubAgentProfile`)

En `backend/src/domain/agents/sub_agent_profiles.py`:

- **Nombre:** Atenea (`AgentRole.SUPERVISOR`).
- **Descripción:** _"Orquestadora estratégica y deidad de la sabiduría técnica que gobierna el consejo arquitectónico, equilibra la innovación con la prudencia, gestiona el flujo HITL y emite veredictos ejecutivos vinculantes."_
- **Color:** `#f59e0b` (Ámbar dorado).
- **Saludo obligatorio:**
  > _"Soy Atenea, la orquestadora estratégica del consejo técnico. Gobierno el debate entre la innovación audaz y la prudencia de ingeniería para forjar arquitecturas sólidas y resilientes. ¿Qué desafío someteremos hoy al escrutinio del consejo?"_
- **Tono:** Solemne, analítico, formal, ecuánime y estrictamente técnico en castellano.
- **Nuevo campo de perfil:**
  ```python
  @dataclass(frozen=True)
  class SubAgentProfile:
      role: AgentRole
      display_name: str
      description: str
      color_hex: str
      system_prompt: str
      uses_rag: bool
      rag_filter: SearchFilter | None = None
      phonetic_aliases: tuple[str, ...] = ()
      supports_hitl: bool = True  # Determina si el agente puede disparar puntos de control HITL
  ```

### 2.2 Prompt de Consolidación Ejecutiva (`_CONSOLIDATION_PROMPT`)

En `backend/src/application/agents/supervisor_agent.py`:
Se actualiza la plantilla al castellano con las siguientes secciones formales:

1. **Resumen Ejecutivo y Dictamen Vinculante:** Decisión arquitectónica final adoptada.
2. **Puntos Clave del Diseño:** Fusión de la audacia de Ícaro y la solidez de Hestia.
3. **Resolución de Enigmas y Mitigación de Riesgos:** Cómo se resuelven las advertencias críticas de Sphinx.
4. **Directivas de Infraestructura y Seguridad:** Criterios de despliegue, observabilidad y hardening de Hefesto.
5. **Referencias al Telar de Arquitectura:** Integración de los flujos y diagramas trazados por Aracne.
6. **Plan de Acción Inmediato:** Próximos pasos para el equipo de desarrollo.

---

## 3. Orquestador y Router Adaptativo (Application Layer)

### 3.1 Clasificador de Intención (Triage Rápido)

Antes de disparar el debate, Atenea realiza una clasificación estructurada y ligera de la intención del usuario:

```json
{
  "mode": "direct_chat" | "single_agent" | "adaptive_debate",
  "target_agent": "diagrammer" | "devops_secops" | "learning" | null,
  "skip_hermes": true | false,
  "reasoning": "Explicación breve de la decisión de enrutamiento"
}
```

1. **Modo Conversación Directa (`direct_chat`):**
   - Saludos, preguntas sobre quién compone el consejo, o dudas generales de alto nivel dirigidas a Atenea.
   - Atenea responde directamente como supervisora en un único turno conversacional sin levantar agentes ni bloquear en HITL.
2. **Modo Especialista Atómico (`single_agent`):**
   - El usuario solicita expresamente una tarea acotada a una disciplina (p. ej. _"hazme un diagrama de secuencia de..."_ $\rightarrow$ Aracne; _"cómo configuro la red en Docker"_ $\rightarrow$ Hefesto; _"asimila este documento"_ $\rightarrow$ Metis).
   - Atenea delega la ejecución directamente al especialista, informando brevemente de la delegación si es necesario.
3. **Modo Debate Adaptativo (`adaptive_debate`):**
   - **Con desambiguación (`skip_hermes: false`):** Si la petición de arquitectura es coloquial o incompleta, comienza en Hermes (`NL_INTERPRETER`) para formalizar requisitos.
   - **Sin desambiguación (`skip_hermes: true`):** Si la petición del usuario ya incluye requisitos detallados, métricas o restricciones técnicas definidas, salta directamente a la fase de arquitectos (`INNOVATOR` y `SENIOR_ARCHITECT`).
   - **Fallback:** En caso de incertidumbre en la clasificación, se mantiene el flujo completo tradicional para garantizar máxima rigurosidad.

---

## 4. Semántica y Ciclo de Vida de Eventos HITL

### 4.1 Modelo de Datos del Evento HITL

En `backend/src/domain/agents/supervisor_events.py`:

```python
class HITLDecision(str, Enum):
    APPROVE = "approve"
    REJECT  = "reject"
    REFINE  = "refine"

@dataclass
class HITLResponse:
    decision: HITLDecision
    feedback: str = ""
    selected_options: list[str] = field(default_factory=list)
    target_agents: list[str] = field(default_factory=list)  # Agentes específicos a donde redirigir el flujo
```

### 4.2 Lógica de Parada HITL por Agente

- Un agente puede sugerir un checkpoint si `profile.supports_hitl == True`.
- Criterios de activación en el flujo adaptativo:
  - **Hermes:** Si su salida contiene preguntas abiertas en `## 4. Preguntas Abiertas / Bloqueantes` (distintas de "Ninguna"), se detiene obligatoriamente en HITL.
  - **Arquitectos (Ícaro y Hestia):** Tras presentar sus dos visiones contrapuestas, se ofrece HITL para que el usuario elija la favorita o seleccione qué aspectos refinar.
  - **Sphinx:** Si identifica riesgos de severidad alta o enigmas sin resolver, emite HITL para validación del usuario.
- **Acción sobre `target_agents`:**
  - Si el usuario aprueba o refina y selecciona `target_agents = ["diagrammer"]`, el orquestador desvía el flujo para invocar a Aracne con el contexto acumulado y el feedback introducido.
  - Si `target_agents` está vacío, el orquestador prosigue con el siguiente paso natural de la cadena planificada.

### 4.2.1 Flujo de Desvío Dinámico (`DIVERT`)
Cuando el usuario acciona **Desviar** (`HITLDecision.DIVERT`) en cualquier punto de control:
1. **Ejecución Concurrente con Emisión de Mensajes:**
   - Se ejecutan en paralelo los agentes indicados en `target_agents`.
   - Se activa obligatoriamente `emit_message=True` en `run_parallel_roles` para que cada agente desviado emita su evento `EventType.MESSAGE` individual con su contenido íntegro y metadatos, mostrándose de inmediato en la ventana del chat.
2. **Nuevo Checkpoint HITL Post-Desvío:**
   - Tras recibir las respuestas de los agentes desviados, Atenea emite un nuevo evento `EventType.HITL_REQUIRED` con metadatos contextuales (`checkpoint: f"after_divert_{lead_agent}"`).
   - El orquestador entra en un bucle interactivo que permite al operador:
     - **`CONSOLIDATE` / `APPROVE`:** Concluir el flujo llamando a la consolidación ejecutiva de Atenea, la cual integra las aportaciones de los agentes desviados.
     - **`FINISH`:** Finalizar inmediatamente el debate con evento `DONE` sin generar consolidación.
     - **`DIVERT`:** Encadenar un nuevo desvío hacia otros agentes del consejo.
     - **`REFINE` / `RETRY`:** Proporcionar nuevas instrucciones o reintentar la fase si se requiere corrección.

### 4.2.2 Emisión Uniforme de Mensajes en Fases Concurrentes y Prevención de Agrupación Monolítica
Para garantizar que todos los agentes asignados a una fase paralela (p. ej. los proponentes Ícaro y Hestia, o especialistas en desvíos) contesten visiblemente de manera individual en el chat:
1. **Emisión de Eventos `MESSAGE` por Agente:**
   - `run_parallel_roles` emite por defecto `emit_message=True` en las propuestas finales de Fase 2, Fase 3 (evaluadores), Fase 4 (implementadores) y desvíos dinámicos.
   - Cada agente publica su propio evento `EventType.MESSAGE` con su avatar, rol y contenido íntegro, permitiendo al usuario apreciar las visiones contrapuestas o complementarias en tarjetas separadas.
2. **Deduplicación en Frontend (`handleHitlRequired`):**
   - El evento `EventType.HITL_REQUIRED` sigue transportando el `combined_content` con separadores `---` para consumo de herramientas y trazabilidad.
   - En el frontend (`debateEventProcessor.ts`), `handleHitlRequired` comprueba si los bloques de las propuestas ya han sido emitidos individualmente mediante eventos `message`. Si todos los bloques válidos ya están en el historial del chat, se evita re-insertar el contenido combinado como un mensaje monolítico bajo el agente líder.

### 4.3 Pre-deliberación Interna de Arquitectura (Actor-Critic con Sphinx)

Para evitar que los arquitectos presenten propuestas inmaduras o vulnerables en el primer HITL:
1. **Ronda 1:** Ícaro y Hestia generan sus borradores en paralelo (`AGENT_STARTED` / `AGENT_COMPLETED`).
2. **Crítica Interna:** Sphinx analiza exhaustivamente las propuestas señalando puntos ciegos, riesgos operacionales y directivas de mejora (`AGENT_STARTED` / `AGENT_COMPLETED`).
3. **Refinamiento Colegiado:** Ícaro y Hestia reciben las objeciones de Sphinx y robustecen sus propuestas en paralelo.
4. **Presentación HITL:** Solo cuando las propuestas han sido contrastadas y enriquecidas internamente, se emite el evento `HITL_REQUIRED` al usuario.
5. **Configuración Dinámica:** Controlado por la variable de entorno `REVIEW_ROUNDS` (por defecto `1`). Configurable a `0` para desactivar la pre-deliberación en entornos de pruebas rápidas o baja latencia.

---

## 5. Diseño de Interfaz de Usuario (Frontend Vue 3)

### 5.1 Traslado del HITL a `ChatPanel.vue`

1. **Retirada de la Columna Derecha:** Se elimina la sección fija de `Manual Override (HITL)` en `AgentTopology.vue` / `AppShell.vue`, liberando la columna lateral derecha exclusivamente para métricas, topología y observabilidad de los agentes.
2. **Tarjeta de Control HITL en el Chat:**
   - Se renderiza un bloque interactivo con borde destacado y brillo ámbar (`border-neon-amber bg-space-900/90`) justo encima del pie de entrada o como el último mensaje activo del asistente.
   - Contiene:
     - Título y avatar del agente emisor que solicita la revisión.
     - Resumen o fragmento clave a validar.
     - **Selector Multiselección de Agentes Destino:** Chips con el color de cada agente (`Hermes`, `Ícaro`, `Hestia`, `Sphinx`, `Hefesto`, `Aracne`, `Metis`) que pueden activarse/desactivarse con un clic.
     - **Botonera de Acción Rápida:**
       - Botón `[ ✓ Aceptar ]` (verde esmeralda).
       - Botón `[ ✗ Rechazar ]` (rojo carmesí).
       - Botón `[ ✏ Refinar ]` (ámbar / focus en el textarea).
3. **Reutilización del Textarea del Chat:**
   - Al estar activo el estado `isHitlRequired`:
     - El placeholder del textarea cambia a: _"Introduce instrucciones de refinamiento para el agente..."_.
     - Al enviar texto (vía botón de enviar o `Enter`), se despacha automáticamente `store.sendHitlDecision('refine', text, selectedTargetAgents)`.
     - El textarea se limpia y el chat retorna a su estado de escucha estándar.

---

## 6. Control de Voz Manos Libres con Vosk (`WakeWordService`)

### 6.1 Extensión de Reconocimiento Acústico en Vosk

En `backend/src/infrastructure/audio/wake_word_service.py`:

- Se añaden comandos de control HITL con sus correspondientes variantes fonéticas en castellano:
  - **Aprobación:** `("aceptar", "aprobar", "adelante", "conforme", "de acuerdo", "ok")`
  - **Rechazo:** `("rechazar", "denegar", "cancela", "cancelar", "descarta", "descartar")`
  - **Refinamiento:** `("refinar", "corregir", "cambiar", "modificar", "ajustar")`

### 6.2 Flujo de Decisión por Voz

1. Cuando `isHitlRequired == true`:
   - Si Vosk decodifica un comando de **Aprobación**: el backend/frontend ejecuta inmediatamente `store.sendHitlDecision('approve', '', selectedTargetAgents)`.
   - Si decodifica un comando de **Rechazo**: ejecuta `store.sendHitlDecision('reject')`.
   - Si decodifica un comando de **Refinamiento**:
     1. El sistema pone el chat en modo refinamiento.
     2. Dispara la grabación de voz por Faster-Whisper para capturar la frase completa de refinamiento del usuario (ej. _"Refinar: enfócate en el rendimiento y pásaselo a Ícaro"_).
     3. Al terminar el silencio, el texto transcrito se analiza para autoseleccionar el agente mencionado y enviar la decisión `refine`.

---

## 7. Plan de Validación y Testing (TDD)

### 7.1 Backend (Pytest)

- `tests/domain/agents/test_sub_agent_profiles.py`:
  - Verificar que el perfil `_SUPERVISOR` tiene prompt en español, saludo mitológico formal y `supports_hitl == True`.
  - Verificar que todos los perfiles tienen el flag `supports_hitl`.
- `tests/application/agents/test_supervisor_agent.py`:
  - Test de enrutamiento directo (conversación sin subagentes).
  - Test de delegación a especialista individual.
  - Test de salto de Hermes cuando los requisitos son completos.
  - Test de HITL con `target_agents` específicos.
  - Test de consolidación ejecutiva en castellano.
- `tests/infrastructure/audio/test_wake_word_service.py`:
  - Detección de comandos de voz HITL ("aceptar", "rechazar", "refinar").
- `tests/presentation/api/ws/test_debate.py`:
  - Verificación del ciclo completo de WebSocket con HITL en el chat y comandos de voz.

### 7.2 Frontend (Vitest)

- `frontend/src/stores/__tests__/debate.spec.ts`:
  - Manejo de `sendHitlDecision` con `targetAgents`.
  - Reacción a comandos de voz de HITL procedentes del WebSocket.
- `frontend/src/components/__tests__/ChatPanel.spec.ts`:
  - Renderizado de la tarjeta interactiva de HITL dentro del panel de chat.
  - Selección y deselección de chips de agentes destino.
  - Envío de refinamiento a través del input principal del chat.
