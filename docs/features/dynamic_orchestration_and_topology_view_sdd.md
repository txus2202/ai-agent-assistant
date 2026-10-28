# Documento de Diseño de Software (SDD): Orquestación Dinámica por Delegación y Visualización del Consejo

## 1. Contexto y Objetivos
Atenea es la **Supervisora Inteligente** del Consejo de Agentes. A diferencia de un pipeline lineal fijo tipo *waterfall* (Fase 1 ➔ Fase 2 ➔ Fase 3 ➔ Fase 4), Atenea debe ser capaz de **planificar y adaptar dinámicamente la ruta de delegación** en función de la intención del usuario y la naturaleza del problema.

Ejemplos de flujos válidos:
- **Flujo Completo Dialéctico:** Requisitos (`Hermes`) ➔ Proponentes (`Ícaro`, `Hestia`) / Revisores (`Sphinx`) ➔ Evaluación (`Sphinx`) ➔ Implementación (`Aracne`, `Hefesto`) ➔ Consolidación (`Atenea`).
- **Flujo Ágil de Especificación e Implementación:** Requisitos (`Hermes`) ➔ Implementación (`Aracne`, `Hefesto`) ➔ Consolidación (`Atenea`).
- **Flujo de Consulta Especializada Directa:** Implementador (`Aracne`) ➔ Consolidación.
- **Flujos en Bucle o Desviados por HITL:** El usuario desvía o refina a agentes específicos en cualquier punto de control.

---

## 2. Especificación Técnica Backend

### 2.1 Triage y Plan de Delegación Dinámico (`TriageDecision`)
En `supervisor_agent.py`, el `classify_intent` evalúa la petición del usuario y genera un `TriageDecision` con:
- `mode`: `"direct_chat"`, `"single_agent"`, `"dynamic_plan"` (o `"adaptive_debate"`).
- `execution_plan`: Lista de roles o etapas planificadas por Atenea para resolver la petición, ej:
  - `["interpreters", "implementers"]`
  - `["proposers", "evaluators"]`
  - `["interpreters", "proposers", "evaluators", "implementers"]`
- `reasoning`: Breve justificación estratégica de Atenea.

### 2.2 Evento de Rastro de Delegación (`execution_trail`)
Cada vez que un agente o etapa es convocado por Atenea:
- Se añade al rastro de ejecución de la sesión (`state.execution_trail: list[str]`).
- Los eventos emitidos por el supervisor incluyen o reflejan los agentes convocados.

---

## 3. Especificación Técnica Frontend (`AgentTopology.vue`)

### 3.1 Visualización del Consejo de Agentes (Por Especialidades, No Fases Rígidas)
En lugar de encabezados fijos de fases secuenciales, el panel presenta al **Consejo de Agentes** agrupado por **Capacidades Funcionales**:
1. **Orquestación & Estrategia:** `Atenea` (Supervisor)
2. **Requisitos & Formalización:** `Hermes` (`interpreters`)
3. **Diseño Arquitectónico:** `Ícaro`, `Hestia` (`proposers`), `Sphinx` (`reviewers`)
4. **Auditoría & Cumplimiento:** `Sphinx` (`evaluators`)
5. **Especialistas Técnicos:** `Aracne` (Diagramas), `Hefesto` (DevSecOps) (`implementers`)
6. **Memoria & Base de Conocimiento:** `Metis` (Vault / RAG)

### 3.2 Indicadores Visuales Clave
- **Rastro de Delegación Activo (Execution Trail):**
  Un componente visual en la parte superior del panel que muestra la ruta seguida en la consulta actual:
  `Atenea ➔ Hermes ➔ Aracne ➔ Atenea`.
- **Badge Concurrente / Paralelo (`⚡ PARALELO`):**
  Cuando dos o más agentes se ejecutan simultáneamente en la misma etapa (ej. Ícaro + Hestia, o Aracne + Hefesto).
- **Estados Dinámicos:**
  - `STANDBY`: En espera.
  - `ACTIVE`: Convocado por Atenea y procesando.
  - Resaltado de borde neón y animación de pulso durante el habla TTS o inferencia.

---

## 4. Metodología TDD
1. **Tests Backend (`test_supervisor_agent.py`):**
   - Validar que Atenea genere y ejecute planes dinámicos (ej. solo intérprete + implementadores, omitiendo proponentes y evaluadores).
   - Validar que el rastro de delegación se actualice correctamente.
2. **Tests Frontend (`AgentTopology.spec.ts`, `debate.spec.ts`):**
   - Validar que `AgentTopology.vue` renderice el consejo organizado por especialidades.
   - Validar que se muestre el rastro de delegación dinámico (*execution trail*).
   - Validar que se identifiquen las ejecuciones paralelas concurrentes.
