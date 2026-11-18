# SDD: Topología Declarativa del Debate, Registro Dinámico de Agentes y Eliminación de AgentRole

## 1. Contexto y Problema
En el sistema inicial de agentes, la arquitectura arrastraba acoplamientos rígidos que impedían la extensibilidad declarativa del consejo:
1. **Duplicidad de `topology.yaml`**: Existían dos copias (`./topology.yaml` y `backend/topology.yaml`), violando la Single Source of Truth (DRY).
2. **Rigidez de `AgentRole` Enum y diccionarios estáticos**:
   - `AgentRole` enumeraba 8 roles fijos (`supervisor`, `nl_interpreter`, etc.).
   - `_ROLE_TO_PROFILE_NAME` y `_PROFILE_NAME_TO_ROLE` forzaban una traducción estática bidireccional entre el enum y los nombres griegos.
   - Un aserto `assert len(_PROFILES) == len(AgentRole)` provocaba que añadir o retirar un perfil de agente sin modificar el enum hiciera que la aplicación fallara en tiempo de carga (`AssertionError`).
   - Múltiples capas (`config.py`, `debate.py`) validaban entradas con `AgentRole(role)`, impidiendo el uso de nuevos agentes.
3. **Acoplamiento en el Orquestador (`supervisor_agent.py`) y en la Topología (`debate_topology.py`)**:
   - Valores por defecto hardcodeados con nombres griegos (`Atenea`, `Hermes`, `Ícaro`, `Hestia`, `Sphinx`, `Aracne`, `Hefesto`).
   - El prompt de triage (`classify_intent`) decía textualmente `"Eres Atenea..."` y listaba únicamente tres especialistas hardcodeados.
   - El modelo de triage usaba `skip_hermes: bool` en lugar de `skip_interpreter: bool`.
   - El prompt de consolidación (`_CONSOLIDATION_PROMPT`) mencionaba por escrito a todos los agentes griegos, ignorando quién participaba realmente en el debate.

## 2. Objetivos
1. **Unificación Canónica de `topology.yaml`**:
   - Una única fuente de verdad situada en la raíz del proyecto (`./topology.yaml`). Se elimina `backend/topology.yaml`.
   - `load_topology()` resuelve canónicamente dicha ruta de forma independiente del directorio de trabajo actual.
2. **Erradicación de `AgentRole` y Registro Dinámico de Agentes (`SubAgentProfile`)**:
   - Eliminación total de `AgentRole`, `_ROLE_TO_PROFILE_NAME`, `_PROFILE_NAME_TO_ROLE` y el aserto `len(_PROFILES) == len(AgentRole)`.
   - `SubAgentProfile` define `id: str` (slug único: `"atenea"`, `"hermes"`, `"icaro"`, etc.) y `display_name: str` (`"Atenea"`, `"Hermes"`, `"Ícaro"`, etc.).
   - Registro dinámico extensible en memoria (`register_profile`, `get_profile`, `get_all_profiles`, `clear_registry`).
   - Búsqueda case-insensitive y normalizada sin tildes por `id`, `display_name` y aliases fonéticos.
3. **Topología Declarativa Agnóstica (`DebateTopology`)**:
   - `DebateTopology` modela los slots funcionales del debate sin defaults fijos a nombres de agentes.
   - Requiere slots explícitos o los carga desde `topology.yaml`. Si falta un slot obligatorio, lanza `ValueError` descriptivo.
   - `validate()` verifica que cada agente declarado exista en el registro y que el agente de `supervisor` tenga `is_supervisor=True`.
4. **Desacoplamiento Integral de `SupervisorAgent`**:
   - `classify_intent` (triage):
     - Prompt dinámico: `f"Eres {supervisor_name}..."`.
     - Especialistas para `single_agent` extraídos dinámicamente de `get_all_profiles()` (filtrando aquellos con `is_supervisor=False`).
     - Campo `skip_interpreter: bool` en `TriageDecision`.
     - Saludos directos detectados contra el nombre/aliases del supervisor activo.
   - `_CONSOLIDATION_PROMPT`:
     - Parametrizado dinámicamente con los participantes reales de la topología activa (`supervisor_name`, `proposers`, `evaluator`, `implementers`).
   - `DebateState`:
     - Métodos genéricos `get_agent_critiques(agent_name)` y `add_agent_critique(agent_name, critique)` sin propiedades acopladas a Sphinx.
   - Firmas de funciones de fases sin strings de nombres fijos por defecto.
5. **Endpoints de Configuración y WebSockets**:
   - `routes/config.py` y `ws/debate.py` validan y resuelven agentes directamente vía `get_profile(identifier)`.
   - Si se añade un nuevo agente al registro, funciona inmediatamente en la API y WebSockets sin tocar código adicional.

## 3. Especificación Técnica por Componentes

### A. Registro Dinámico de Agentes (`backend/src/domain/agents/sub_agent_profiles.py`)
```python
@dataclass(frozen=True)
class SubAgentProfile:
    id: str
    display_name: str
    description: str
    color_hex: str
    system_prompt: str
    uses_rag: bool
    rag_filter: SearchFilter | None = None
    phonetic_aliases: tuple[str, ...] = ()
    supports_hitl: bool = True
    is_supervisor: bool = False

    @property
    def name(self) -> str:
        return self.display_name
```
Funciones de registro:
- `register_profile(profile: SubAgentProfile) -> None`: Registra un perfil en el catálogo indexando por `id`, `display_name`, versiones normalizadas y aliases.
- `get_profile(identifier: str) -> SubAgentProfile`: Obtiene el perfil resolviendo por `id`, `display_name` o alias. Lanza `KeyError` si no existe.
- `get_all_profiles() -> list[SubAgentProfile]`: Retorna todos los perfiles registrados en orden de registro.
- `reset_default_profiles() -> None`: Restaura el catálogo de agentes por defecto del sistema.

### B. Topología de Debate (`backend/src/domain/agents/debate_topology.py`)
```python
@dataclass(frozen=True)
class DebateTopology:
    supervisor: str
    interpreter: str
    proposers: tuple[str, ...]
    reviewer: str
    evaluator: str
    implementers: tuple[str, ...]
    review_rounds: int = 1
```
- `load_topology(path: Path | str | None = None) -> DebateTopology`:
  1. Si `path` es provisto, usa esa ruta.
  2. Si existe la variable de entorno `TOPOLOGY_FILE`, usa esa ruta.
  3. Por defecto, busca en `<project_root>/topology.yaml`.
  4. Lanza `FileNotFoundError` si el fichero no existe.
  5. Parsea el YAML y valida slots requeridos.

### C. Orquestador (`backend/src/application/agents/supervisor_agent.py`)
- `classify_intent`:
  - Recibe `supervisor_name: str` y `available_specialists: list[SubAgentProfile]`.
  - Construye el prompt de triage dinámicamente.
  - Retorna `TriageDecision(mode=..., target_agent=..., skip_interpreter=..., reasoning=...)`.
- `_CONSOLIDATION_PROMPT`:
  - Plantilla dinámica estructurada con placeholders `{supervisor_name}`, `{proposers_str}`, `{reviewer_name}`, `{evaluator_name}`, `{implementers_str}`, `{debate_context}`.

### D. Rutas y Presentación
- `backend/src/presentation/api/routes/config.py`:
  - `/api/config/agents`: Itera sobre `get_all_profiles()`. El campo `"id"` es `profile.id`.
  - `/api/config/agents/{role}`: Resuelve con `get_profile(role)`. Si lanza `KeyError`, responde 404 `"Agent not found"`.
  - `PUT /api/config/agents/{role}`: Valida con `get_profile(role)` antes de guardar en `SqliteAgentConfigRepository`.
- `backend/src/presentation/api/ws/debate.py`:
  - Resuelve agentes con `get_profile(target_agent)` y envía `profile.display_name`.

## 4. Plan de Pruebas (TDD)
1. **Dominio (`test_sub_agent_profiles.py`)**:
   - Registro de perfiles dinámicos y recuperación por ID, display_name y alias.
   - Añadir dinámicamente un nuevo agente (`"Apolo"`) y verificar que se recupera sin errores.
   - Retirar un perfil y verificar que no afecta al resto de perfiles.
   - Comprobar que `is_supervisor` es `True` para Atenea y `False` para los demás.
2. **Dominio (`test_debate_topology.py`)**:
   - Carga desde la raíz `./topology.yaml`.
   - Error si falta algún slot requerido.
   - Rechazo si el supervisor no tiene `is_supervisor=True`.
   - Rechazo si un agente no existe en el registro.
   - Carga con topología personalizada con agentes dinámicos.
3. **Aplicación (`test_supervisor_agent.py`)**:
   - Triage dinámico con `skip_interpreter`.
   - Consolidación dinámica con nombres de la topología inyectada.
   - Flujo completo con topología customizada.
4. **Presentación (`test_config.py`, `test_debate.py`)**:
   - GET/PUT en `/api/config/agents/{role}` funcionando con nuevos agentes dinámicos sin Enum.

---

## 5. Fase 2 — Catálogo Externo de Agentes y Neutralidad de Dominio

### 5.1 Problema residual
Tras la fase 1 seguían existiendo acoplamientos al *consejo actual* y a su *dominio* (arquitectura de software):
- `sub_agent_profiles.py` definía en código `_SENIOR_ARCHITECT`, `_THE_JUDGE`, `_DEVOPS_SECOPS`, etc. y `_DEFAULT_PROFILES`.
- `supervisor_agent.py`: `skip_hermes` (alias), defaults `"Atenea"`/`"Hermes"`/`"Sphinx"`…, propiedades `sphinx_critiques`/`judge_history`, variables `judge_content`, docstring de cabecera con los agentes actuales, textos como `"los arquitectos proponentes"` o `"jueza ... de arquitectura"` y ejemplos de dominio (Redis).
- `ws/debate.py` trataba `"learning"/"metis"` como caso especial por nombre; `wake_word.py` tenía fallback `"Atenea"`; los prompts de STT (`config.py`, `local_audio_service.py`) listaban los nombres de los agentes.

### 5.2 Decisiones
1. **Solo el supervisor vive en código** (`_SUPERVISOR`, agente de arranque mínimo para que el sistema siempre tenga orquestador). El resto de agentes se declaran en **`./agents.yaml`** (raíz del proyecto, junto a `topology.yaml`; ruta sobrescribible con `AGENTS_FILE`).
2. `agents.yaml` contiene una lista `agents:` con los mismos campos de `SubAgentProfile` (`id`, `display_name`, `description`, `color_hex`, `system_prompt`, `uses_rag`, `rag_filter`, `phonetic_aliases`, `supports_hitl`, `is_supervisor`, `can_ingest_documents`).
3. `load_profiles_from_file(path) -> list[SubAgentProfile]` valida campos obligatorios (`ValueError` descriptivo) e ids duplicados. El registro se inicializa con `_SUPERVISOR` + el catálogo del fichero; `reset_default_profiles()` hace lo mismo.
4. Nuevo campo **`can_ingest_documents: bool = False`** en el perfil: sustituye al caso especial `"learning"/"metis"` de `ws/debate.py`. El WebSocket resuelve el perfil y enruta por flags (`is_supervisor`, `can_ingest_documents`), no por nombre.
5. **`SupervisorAgent` sin nombres ni dominio**:
   - `TriageDecision.skip_interpreter` (sin alias `skip_hermes`); la clave JSON del triage es `skip_interpreter`.
   - `classify_intent(..., supervisor_name, interpreter_name)` y las funciones de fase reciben los nombres **obligatoriamente** (sin defaults).
   - `DebateState` solo expone `add_agent_critique`/`get_agent_critiques`; se eliminan `sphinx_critiques` y `judge_history`.
   - Textos neutros: *agentes proponentes / agente revisor / agente evaluador / agentes de implementación*, "solución" en vez de "arquitectura", sin ejemplos de dominio.
   - `_CONSOLIDATION_PROMPT` con secciones genéricas.
6. `wake_word.py`: sin fallback con nombre. STT: el *initial prompt* no incluye nombres; `LocalAudioService` añade en tiempo de transcripción los `display_name` del registro.
7. El prompt del `_SUPERVISOR` en código no enumera agentes concretos ni las secciones de consolidación específicas del dominio.

### 5.3 Plan de pruebas (TDD) fase 2
- `test_sub_agent_profiles.py`: solo nombres genéricos (`alpha`, `beta`…); registro/baja dinámicos, carga desde YAML temporal, validaciones (campo faltante, id duplicado), `can_ingest_documents`, inmutabilidad. Un único test de integración comprueba invariantes estructurales del `agents.yaml` real (todos los ids de `topology.yaml` existen) sin citar nombres.
- `tests/application/agents/conftest.py`: fixture que apunta `AGENTS_FILE`/`TOPOLOGY_FILE` a ficheros de test con agentes genéricos; `test_supervisor_agent.py` y `test_sub_agent_runner.py` usan esos nombres.
- `TriageDecision`/`classify_intent`: sin atributo `skip_hermes`; el prompt lista solo los especialistas registrados.
- `test_debate.py` (WS): enrutado por `can_ingest_documents`.
- `test_local_audio_service.py`: el prompt incluye los nombres del registro de forma dinámica.

---

## 6. Fase 3 — Unificación completa del Supervisor en `agents.yaml`

### 6.1 Motivación
Tener `BUILTIN_SUPERVISOR` embebido en Python con el nombre, saludo y prompt de Atenea mantenía una fuga de acoplamiento a nivel de persona y dominio. Siguiendo el principio de cero acoplamiento:
- `agents.yaml` es la **única fuente de verdad** para todos los perfiles de agentes, incluyendo el supervisor.
- En código Python no existe ningún agente ni persona hardcodeada.

### 6.2 Especificación
1. **`agents.yaml` incluye al supervisor:**
   Se añade una entrada con `is_supervisor: true` (por defecto Atenea, con su prompt y configuración).
2. **Eliminación de `BUILTIN_SUPERVISOR` en código:**
   `backend/src/domain/agents/sub_agent_profiles.py` elimina `BUILTIN_SUPERVISOR`.
3. **Validación de presencia obligatoria de supervisor:**
   `load_profiles_from_file(catalog_path)` verifica obligatoriamente que al menos un agente en el catálogo tenga `is_supervisor: true`. Si no existe ninguno, lanza `ValueError(f"Agent catalog {catalog_path} must define at least one supervisor agent (is_supervisor: true)")`.
4. **Inicialización y Reset del Registro:**
   `reset_default_profiles()` limpia el registro y carga íntegramente los perfiles desde `load_profiles_from_file(default_agents_file())`.
5. **Auditoría Estática ([`test_decoupling_guard.py`](backend/tests/application/agents/test_decoupling_guard.py)):**
   Se añade la comprobación de que `sub_agent_profiles.py` no contiene `BUILTIN_SUPERVISOR`, ni `"Atenea"`, ni texto de personas hardcodeadas.
