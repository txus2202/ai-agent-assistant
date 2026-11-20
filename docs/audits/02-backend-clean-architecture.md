# Auditoría 02 — Backend, Clean Architecture y Calidad de Código

## ✅ Lo que está bien hecho

- **Núcleo de dominio puro en entidades y excepciones (`backend/src/domain/entities/`, `backend/src/domain/exceptions.py`, `backend/src/domain/value_objects/`):** `Agent`, `User`, `DocumentChunk` y `SearchFilter` son modelos limpios sin dependencias de frameworks. `SearchFilter.__post_init__` garantiza hashabilidad e inmutabilidad convirtiendo listas en tuplas. `exceptions.py` centraliza una capa anticorrupción explícita (`LLMProviderError`, `RepositoryError`, `ExtractionError`, jerarquía de `AuthenticationError`/`AuthorizationError`).
- **Caso de uso `RunAgentTask` ejemplar (`backend/src/application/use_cases/run_agent_task.py`):** Cero imports externos o de capas superiores, inyección por constructor sobre puertos (`IAgentRepository`, `ILLMProvider`), DTOs inmutables (`RunAgentTaskInput`, `RunAgentTaskOutput`) y degradación controlada.
- **Seguridad criptográfica en adaptadores (`backend/src/infrastructure/security/`):** `Argon2idPasswordHasher` aplica parámetros recomendados por OWASP con protección frente a DoS por longitud (`MAX_PASSWORD_LENGTH = 128`) y null-bytes; `JwtTokenService` valida fail-fast longitud mínima de clave (32 bytes), rechaza secretos por defecto conocidos y verifica `iss`, `aud` y `token_version`.
- **Protección contra enumeración y condiciones de carrera en `AuthService` (`backend/src/application/services/auth_service.py`):** Ejecuta Argon2id en `asyncio.to_thread`, verifica `_DUMMY_HASH` cuando el usuario no existe para igualar tiempos de respuesta, serializa el bootstrap inicial con `asyncio.Lock` y protege invariantes críticas (`LastAdminError`, `SelfModificationError`).
- **Guarda arquitectónica de agnósticismo de agentes (`backend/tests/application/agents/test_decoupling_guard.py`):** Prueba automatizada que evita acoplamiento léxico a nombres concretos de agentes (`Atenea`, `Hermes`, etc.) en la orquestación genérica.
- **Estrategia Stale-While-Revalidate + Lock distribuido en `models.py` (`backend/src/presentation/api/routes/models.py`):** Implementa caché de catálogo de modelos con probing gratuito (`count_tokens` en Gemini/Anthropic) y bloqueo atómico en BD (`acquire_probe_lock`) evitando latencia de arranque y consumo redundante de tokens.

---

### [P1] Violaciones de la Regla de Dependencia en `domain/`: YAML, `os`, I/O al importar y estado global mutable
- **Impacto:** Arquitectura | Acoplamiento
- **Target File(s):** `backend/src/domain/agents/sub_agent_profiles.py` (L24-L30, L54-L93, L135-L280), `backend/src/domain/agents/debate_topology.py` (L18-L22, L53-L110), `backend/src/domain/entities/task.py` (L13, L110-L118)
- **Current State (Problema):**
  1. `sub_agent_profiles.py` importa `yaml` (`PyYAML`) y `os`, lee y parsea `./agents.yaml` del disco y ejecuta `reset_default_profiles()` **en tiempo de importación** (L280), manteniendo un registro global mutable (`_REGISTRY_MAP`, `_ALL_PROFILES`) dentro de `domain/`. Además en L57 acopla lógica de dominio a un ID concreto (`self.id in ("fidias", "fídias")`), burlando el guard de nombres capitalizados.
  2. `debate_topology.py` importa `yaml` y `os`, resuelve rutas con `os.environ.get("TOPOLOGY_FILE")` y lee `topology.yaml` desde disco dentro de `domain/`.
  3. `task.py` importa `os` y lee `os.getenv("TASK_PROMPT_MAX_LENGTH", 10_000)` dentro de `Task._validate_prompt`.
- **Desired Outcome (Objetivo):** Capa `domain/` 100% pura (solo Python stdlib sin I/O, `os`, ni librerías de serialización como `PyYAML`), con repositorios/puertos (`IAgentProfileRepository`, `ITopologyRepository`) cargados desde `infrastructure/` e inyectados en `application/`/`presentation/`.
- **Actionable Steps for Agent:**
  1. Dejar en `domain/agents/` exclusivamente los Value Objects puros (`SubAgentProfile`, `DebateTopology`) y funciones puras de validación/formateo (`format_team_roster` recibiendo la colección de perfiles como argumento en lugar de leer globals). Eliminar el fallback `self.id in ("fidias", "fídias")` apoyándose únicamente en la capacidad declarativa `"image_viewer" in self.tools`.
  2. Definir puertos `IAgentCatalogRepository` / `ITopologyProvider` en `domain/ports/` y mover el parsing YAML (`load_profiles_from_file`, `load_topology`) y la resolución de `AGENTS_FILE`/`TOPOLOGY_FILE` a adaptadores en `infrastructure/config/` (p. ej. `yaml_agent_catalog.py`), cacheados en el composition root.
  3. Inyectar `max_length: int = 10_000` como parámetro en `Task.__init__` / `_validate_prompt` (leyendo `TASK_PROMPT_MAX_LENGTH` en `Settings`, no en `domain/entities/task.py`).
  4. Actualizar los tests en `backend/tests/domain/` y `backend/tests/application/` y verificar con `pytest`.

---

### [P1] Violaciones de la Regla de Dependencia hacia `infrastructure/` y `presentation/` desde `application/` e `infrastructure/`
- **Impacto:** Arquitectura | Acoplamiento
- **Target File(s):** `backend/src/application/agents/supervisor_agent.py` (L707-L708), `backend/src/application/agents/sub_agent_runner.py` (L29, L234, L242), `backend/src/application/services/ingest_vault.py` (L20, L86), `backend/src/application/services/learn_from_source.py` (L26-L29, L87-L94), `backend/src/infrastructure/llm/registry.py` (L14), `backend/src/infrastructure/image_generation/service.py` (L85)
- **Current State (Problema):**
  1. `application/agents/supervisor_agent.py` (L707) importa `from src.presentation.api.config import get_settings`, invirtiendo la dirección de dependencias (Application -> Presentation).
  2. `application/agents/sub_agent_runner.py` (L29) importa directamente la clase concreta `ImageGenerationService` de `infrastructure/` y la invoca estáticamente.
  3. `application/services/ingest_vault.py` (L20) importa directamente `ObsidianParser` de `infrastructure/rag/`.
  4. `application/services/learn_from_source.py` (L26-L29) importa las 4 implementaciones concretas (`ImageExtractor`, `MarkdownExtractor`, `PDFExtractor`, `URLExtractor`) de `infrastructure/learning/`.
  5. `infrastructure/llm/registry.py` (L14) e `infrastructure/image_generation/service.py` (L85) importan `get_settings` desde `presentation/api/config.py`, acoplando la capa Infrastructure a FastAPI/Presentation.
- **Desired Outcome (Objetivo):** Cumplimiento estricto de Arquitectura Hexagonal (`presentation -> application -> domain <- infrastructure`): cero imports de `infrastructure` o `presentation` desde `application`, y cero imports de `presentation` desde `infrastructure`.
- **Actionable Steps for Agent:**
  1. Introducir puertos en `domain/ports/`: `IImageGenerator` (implementado por `ImageGenerationService`), `IDocumentParser` (implementado por `ObsidianParser`), y `ISourceExtractor` / mapa `dict[SourceType, ISourceExtractor]` (implementado por los 4 extractores).
  2. Pasar `default_provider`, `default_model` y `review_rounds` explícitamente como parámetros o DTO de configuración a `SupervisorAgent.run(...)` desde `presentation/`, eliminando `from src.presentation.api.config import get_settings` en `supervisor_agent.py`.
  3. Mover la configuración tipada (`AppSettings` o `LLMSettings` / `ImageSettings`) fuera de `presentation` o inyectar claves/configuración por constructor en `infrastructure/llm/registry.py` y `ImageGenerationService` desde el composition root.
  4. Verificar con tests de arquitectura de imports y `pytest`.

---

### [P1] Duplicidad del registro de LLMs e inconsistencia estructural en `domain/ports/`
- **Impacto:** Arquitectura | Clean Code
- **Target File(s):** `backend/src/application/services/llm_provider_registry.py` (L16-L76), `backend/src/infrastructure/llm/registry.py` (L17-L71), `backend/src/domain/ports/*`
- **Current State (Problema):**
  1. Coexisten dos registros de LLMs: `application/services/llm_provider_registry.py` (`LLMProviderRegistry`, creado según ADR-013, con método obsoleto `provider.list_models()` sin manejo de caché ni uso en la API) e `infrastructure/llm/registry.py` (`get_llm_provider()`, que instancia un nuevo adaptador/cliente HTTP SDK en cada llamada desde `ws/debate.py`, `routes/models.py` y `routes/learning.py`!).
  2. Los puertos en `domain/ports/` mezclan `ABC` (`IAgentRepository`, `IDebateRepository`, `IDocumentStore`, `ILLMProvider`, etc.) con `Protocol` (`IUserRepository`, `IPasswordHasher`, `ITokenService`, `IModelCacheRepository`, `IObservabilityService`), llegando a usar `@abstractmethod` dentro de `Protocol` (`user_repository_port.py`, `password_hasher_port.py`, `token_service_port.py`).
  3. `domain/ports/observability_port.py` (L109-L190) contiene una implementación concreta (`NoOpObservabilityService`) dentro de la carpeta de puertos del dominio.
- **Desired Outcome (Objetivo):** Un único `LLMProviderRegistry` construido en el composition root durante `lifespan` reutilizando adaptadores/clientes HTTP, puertos consistentes en `domain/ports/` (todos `Protocol` o todos `ABC`) y `NoOpObservabilityService` movido a `infrastructure/observability/`.
- **Actionable Steps for Agent:**
  1. Construir e inicializar `LLMProviderRegistry` una sola vez en `presentation/api/dependencies/llm.py` (o `app.state`), reutilizando instancias configuradas (`GeminiAdapter`, `OpenAIAdapter`, `AnthropicAdapter`) e inyectando `registry.get` como `llm_factory` en `SupervisorAgent` y endpoints; retirar la función global `get_llm_provider` en `infrastructure/llm/registry.py` tras migrar llamadas.
  2. Estandarizar `domain/ports/` usando `@runtime_checkable class ... (Protocol)` de forma uniforme (sin `@abstractmethod` redundantes) o `ABC`, y mover `NoOpObservabilityService` a `infrastructure/observability/noop_observability.py`.
  3. Actualizar `backend/tests/application/test_llm_provider_registry.py` y tests de puertos, ejecutando `pytest`.

---

### [P1] Brechas en `test_decoupling_guard.py` y defecto silencioso en `test_composition_root.py` y `tests/doubles.py`
- **Impacto:** Arquitectura | Clean Code
- **Target File(s):** `backend/tests/application/agents/test_decoupling_guard.py` (L21-L64), `backend/tests/presentation/api/dependencies/test_composition_root.py` (L11-L62), `backend/tests/doubles.py` (L19-L36)
- **Current State (Problema):**
  1. `test_decoupling_guard.py` solo busca nombres de display (`Atenea`, `Fídias`, etc.) como subcadenas, pero:
     - **No comprueba la Regla de Dependencia por AST** (por eso pasaron 7 violaciones graves de `domain -> yaml/os` y `application -> infrastructure/presentation`).
     - No detectó IDs en minúsculas (`"fidias"`/`"fídias"` en `sub_agent_profiles.py:57`), ni `"learning"` hardcoded en `routes/learning.py:65`, ni los nombres de dominios hardcoded en `ws/debate.py:101-108, 448-450`.
     - Falla su propósito de neutralidad en `ws/debate.py` y `sub_agent_runner.py` al dejar acoplamientos implícitos.
  2. En `test_composition_root.py:14`, el test instancia `Settings(db_path=str(tmp_path / "sqlite.db"), ...)`. Ese campo no existe en `Settings` (se llama `sqlite_db_path`), y como `Settings` tiene `extra="ignore"`, Pydantic lo descarta silenciosamente y el test acaba conectándose al archivo real `backend/atenea.db` del workspace. Además no verifica la composición de `IDebateRepository`, `IAgentConfigRepository`, `IModelCacheRepository` ni `IDocumentStore`.
  3. En `tests/doubles.py`, `FixedResponseProvider.list_models(self)` y `FailingProvider.list_models(self)` no aceptan el parámetro `probe: bool = True` exigido por `ILLMProvider.list_models`.
- **Desired Outcome (Objetivo):** Guardias arquitectónicas basadas en AST que bloqueen regresiones de dependencias entre capas, tests de composition root aislados en `tmp_path` validando todos los puertos, y test doubles compatibles con el contrato completo.
- **Actionable Steps for Agent:**
  1. Ampliar `test_decoupling_guard.py` con un test basado en `ast` que valide: (a) `src/domain/` no importa `yaml`, `os`, `fastapi`, `pydantic`, `chromadb`, `sqlite3`, ni capas externas; (b) `src/application/` no importa `src.infrastructure.*` ni `src.presentation.*`; (c) `src/infrastructure/` no importa `src.presentation.*`.
  2. Corregir `db_path=` -> `sqlite_db_path=` en `test_composition_root.py` y añadir aserciones sobre todos los repositorios y `app.state`.
  3. Actualizar `FixedResponseProvider.list_models(self, probe: bool = True)` y `FailingProvider.list_models(self, probe: bool = True)` en `tests/doubles.py`.
  4. Ejecutar `pytest tests/application/agents/test_decoupling_guard.py tests/presentation/api/dependencies/test_composition_root.py`.

---

### [P1] Operaciones síncronas bloqueantes dentro de corrutinas `async` (Event Loop Starvation)
- **Impacto:** Rendimiento | Escalabilidad
- **Target File(s):** `backend/src/application/agents/sub_agent_runner.py` (L227-L233), `backend/src/application/agents/supervisor_agent.py` (L177, L732), `backend/src/presentation/api/routes/learning.py` (L77-L116, L120-L174), `backend/src/presentation/api/routes/config.py` (L80-L199), `backend/src/presentation/api/routes/observability.py` (L41-L56), `backend/src/presentation/api/ws/debate.py` (L150-L175, L241-L290), `backend/src/presentation/api/ws/wake_word.py` (L62, L111-L112), `backend/src/infrastructure/persistence/sqlite_user_repository.py` (L69-L158)
- **Current State (Problema):**
  Múltiples rutas y handlers `async def` ejecutan trabajo pesado de I/O o CPU directamente en el event loop de `uvicorn`:
  - `SubAgentRunner.run` llama síncronamente a `cls._retrieve_rag_context` -> `ChromaDBDocumentStore.search` (que calcula embeddings locales con PyTorch/`sentence-transformers` en CPU + lectura ChromaDB).
  - `SupervisorAgent` (`_debate_generator:732`) llama síncronamente a `classify_intent(...)` -> `llm_provider.complete(...)` (petición HTTP síncrona bloqueante).
  - `routes/learning.py` (`learn_session`) instancia `ChromaDBDocumentStore` (cargando modelo `all-MiniLM-L6-v2` en cada request) y ejecuta `LearnFromSession.run(...)` (llamada LLM + escritura disco + re-ingesta completa del Vault) síncronamente en una ruta `async def`.
  - `ws/debate.py` (`DebateWebSocketHandler.__init__`) instancia `ChromaDBDocumentStore` en cada conexión WS y ejecuta SQLite y `langfuse.flush()` / `score_trace()` (HTTP síncrono) dentro de `send_event` y `hitl_callback`.
  - `ws/wake_word.py` ejecuta decodificación C++ de Vosk (`process_chunk`) en el event loop.
  - `SQLiteUserRepository` declara `async def` en todos sus métodos pero ejecuta `sqlite3.connect` síncrono.
  - `routes/observability.py` (`get_stats`) ejecuta `subprocess.check_output(["vm_stat"])` (en Darwin) o lectura `/proc/meminfo` de forma síncrona en `async def`; `routes/config.py` lee YAML y consulta SQLite en `async def`.
- **Desired Outcome (Objetivo):** Cero llamadas bloqueantes en el event loop `async`: `ChromaDBDocumentStore` compartido como singleton en `app.state` (evitando recarga de modelo por request/WS), offload explícito vía `asyncio.to_thread` (o adaptadores nativos `async`/`httpx.AsyncClient` y `aiosqlite`/`asyncpg`).
- **Actionable Steps for Agent:**
  1. Convertir `ChromaDBDocumentStore` en una dependencia singleton gestionada en `lifespan` (`app.state.document_store`), evitando cargarlo por cada request de `/learning/session` o conexión `/ws/debate`.
  2. Envolver `cls._retrieve_rag_context`, `classify_intent`, `LearnFromSession.run`, `VaultDomainService.*`, `wake_word_service.process_chunk`, `observability.*` (especialmente `_flush_client`) y los repositorios síncronos en `asyncio.to_thread(...)` (o convertir `routes/learning.py`, `routes/config.py`, `routes/history.py` a funciones `def` síncronas si no requieren `await` explícito).
  3. Hacer que `SQLiteUserRepository` ejecute sus operaciones `sqlite3` dentro de `await asyncio.to_thread(...)` para cumplir honestamente el contrato `async` de `IUserRepository`.
  4. Verificar latencia concurrente mediante test con `asyncio` / `pytest-asyncio` asegurando que un `/health` responde en < 10 ms durante ejecución simulada de RAG/triage/learning.

---

### [P1] Path Traversal en `attachments` vía WebSocket y vulnerabilidad SSRF en `URLExtractor`
- **Impacto:** Seguridad
- **Target File(s):** `backend/src/presentation/api/ws/debate.py` (L347-L373, L816), `backend/src/presentation/api/routes/upload.py` (L15-L60), `backend/src/infrastructure/learning/url_extractor.py` (L43-L47)
- **Current State (Problema):**
  1. En `ws/debate.py` (L816), el cliente envía una lista arbitraria `attachments` con rutas de archivo en el mensaje JSON `start`. `DebateWebSocketHandler._learn_single_attachment` pasa esa ruta sin validar a `LearnFromSource.run(source=attachment_path, ...)`, que abre y extrae texto de cualquier PDF/Markdown/Imagen legible por el usuario del contenedor (p. ej. `/app/.env`, `/app/data/atenea.db` o ficheros de otros usuarios en `/tmp/atenea_uploads`).
  2. En `routes/upload.py` (L16), `MAX_FILE_SIZE_MB = 50` está hardcodeado en lugar de usar `settings.max_learn_file_mb`, y los archivos subidos a `TEMP_UPLOAD_DIR` nunca se eliminan ni se vinculan al `user_id`.
  3. En `url_extractor.py` (L44), `httpx.get(url, follow_redirects=True, timeout=30)` permite SSRF contra servicios internos de `data-net` (`http://postgres:5432`, `http://clickhouse:8123`, `http://minio:9000`, `http://169.254.169.254/latest/meta-data/`).
- **Desired Outcome (Objetivo):** Validación estricta de rutas de adjuntos confinadas al directorio de uploads (preferiblemente por `file_id` opaco asociado al `user_id` + borrado post-procesado) y protección SSRF en `URLExtractor`.
- **Actionable Steps for Agent:**
  1. Cambiar `POST /upload` para usar `settings.max_learn_file_mb`, guardar archivos en un subdirectorio por usuario (o devolver un `attachment_id` opaco registrado con `user_id` y TTL) y validar en `ws/debate.py` que la ruta resuelta (`Path.resolve().is_relative_to(user_upload_dir)`) pertenece al directorio seguro del usuario, eliminando el temporal tras el procesamiento.
  2. En `URLExtractor.extract`: validar que el esquema sea estrictamente `http`/`https`, resolver DNS (`socket.getaddrinfo`) rechazando direcciones privadas, loopback, multicast y link-local (`ipaddress.ip_address(...).is_private` / `is_loopback` / `is_link_local` / `is_reserved`), y desactivar redirecciones automáticas re-validando cada hop (`follow_redirects=False` con loop acotado) además de limitar `max_bytes` de descarga.
  3. Añadir tests de seguridad en `backend/tests/presentation/api/ws/test_debate.py` y `backend/tests/infrastructure/test_extractors.py` verificando rechazo de `../` y IPs internas (`127.0.0.1`, `169.254.169.254`, `10.0.0.1`).

---

### [P2] Condición de carrera en `_last_usage`, round-trips redundantes en `GeminiAdapter` y `Any` sin importar
- **Impacto:** Rendimiento | Clean Code | Arquitectura
- **Target File(s):** `backend/src/infrastructure/llm/gemini_adapter.py` (L57-L105, L141-L147), `backend/src/infrastructure/llm/openai_adapter.py` (L41-L58, L97-L99), `backend/src/infrastructure/llm/anthropic_adapter.py` (L41-L65), `backend/src/domain/ports/llm_provider.py` (L42-L64), `backend/src/infrastructure/rag/chroma_document_store.py` (L168)
- **Current State (Problema):**
  1. Los tres adaptadores almacenan tokens en el atributo mutable de instancia `self._last_usage`, y `SubAgentRunner._calculate_usage` (L197) llama `hasattr(llm_provider, "get_last_usage")`. Si dos sub-agentes corren en paralelo (`asyncio.gather`) compartiendo instancia del adaptador, `self._last_usage` sufre una **race condition** y mezcla métricas de tokens entre agentes. Además `get_last_usage` ni siquiera forma parte del puerto `ILLMProvider`.
  2. `GeminiAdapter.complete()` ejecuta `count_tokens()` previo a **cada** llamada `generate_content()`, duplicando la latencia de red en el 99% de los prompts (< 32,768 tokens). Cuando supera 32,768 tokens, crea una caché con TTL de 1 hora, hace una petición y la borra inmediatamente (3 round-trips para una sola inferencia sin reutilización entre llamadas!).
  3. `gemini_adapter.py:147` (`model: Any`) y `chroma_document_store.py:168` (`val: Any`) utilizan `Any` sin importarlo de `typing` (ocasionando error en `mypy`/`ruff` si se activan).
  4. `AnthropicAdapter` no sobrescribe `complete_stream` (cae en fallback bloqueante de 1 solo chunk) ni `complete_image`.
- **Desired Outcome (Objetivo):** Retorno estructurado o hilo-seguro de métricas de uso en el puerto LLM, eliminación de `count_tokens()` previo por defecto en Gemini y tipado estático limpio.
- **Actionable Steps for Agent:**
  1. Ampliar `ILLMProvider` (o introducir `LLMCompletion(content: str, usage: dict[str, int])` con método compat `complete(...)`) o almacenar `_last_usage` en `contextvars.ContextVar` / devolver `(content, usage)` para eliminar cualquier estado compartido mutable por instancia.
  2. En `GeminiAdapter.complete()`: usar heurística rápida `len(prompt) // 4 >= 30000` antes de invocar `count_tokens()`, y solo crear caches explícitas cuando haya contexto reutilizable entre múltiples turnos/agentes (o eliminar el ciclo crear+usar+borrar de un solo uso).
  3. Importar `Any` desde `typing` en `gemini_adapter.py` y `chroma_document_store.py`, e implementar `complete_stream` nativo en `AnthropicAdapter`.
  4. Verificar con `mypy src` y `pytest tests/infrastructure/test_llm_adapters.py`.

---

### [P2] Complejidad $O(N^2)$ en `SqliteDebateRepository.append_event`, falta de WAL y fugas de descriptores SQLite
- **Impacto:** Rendimiento | Escalabilidad | Clean Code
- **Target File(s):** `backend/src/infrastructure/persistence/sqlite_debate_repository.py` (L46-L62, L142-L153), `backend/src/infrastructure/persistence/sqlite_user_repository.py` (L33-L158), `backend/src/infrastructure/persistence/sqlite_agent_config_repository.py` (L187-L198), `backend/src/infrastructure/persistence/sqlite_agent_repository.py` (L120-L131), `backend/src/infrastructure/persistence/sqlite_task_repository.py` (L143-L154), `backend/src/infrastructure/persistence/sqlite_model_cache_repository.py` (L45-L56)
- **Current State (Problema):**
  1. `SqliteDebateRepository.append_event()` (L46-L62) realiza un ciclo read-modify-write sobre toda la columna `events_json`: lee el texto JSON completo de la fila, ejecuta `json.loads()`, hace `.append()`, `json.dumps()` y reescribe todo el blob. Un debate de $N$ eventos incurre en **$O(N^2)$** bytes parseados, serializados y escritos a disco, además de perder actualizaciones bajo concurrencia al no usar `BEGIN IMMEDIATE`.
  2. Los 6 repositorios SQLite duplican la lógica de `_connection()`, **ninguno** configura `PRAGMA journal_mode=WAL` ni `PRAGMA synchronous=NORMAL` ni `PRAGMA foreign_keys=ON` (solo `SqliteModelCacheRepository` especifica `timeout=10.0`), provocando `OperationalError: database is locked` bajo escrituras concurrentes.
  3. `SQLiteUserRepository` utiliza `with sqlite3.connect(self._db_path) as conn:` directamente sin `conn.close()` en `finally`; en la stdlib de Python, el context manager de `sqlite3.Connection` solo hace `commit`/`rollback`, **no cierra la conexión**, filtrando descriptores de archivo.
- **Desired Outcome (Objetivo):** Tabla normalizada `debate_events` (inserción $O(1)$ append-only), helper compartido de conexión SQLite con modo WAL y cierre garantizado.
- **Actionable Steps for Agent:**
  1. Extraer un helper/mixin compartido `SqliteConnectionManager` en `infrastructure/persistence/sqlite_base.py` que abra la conexión con `timeout=15.0`, active `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000;`, gestione `commit/rollback` y garantice `conn.close()` en `finally`.
  2. Migrar `SqliteDebateRepository` a una tabla `debate_events(id INTEGER PRIMARY KEY AUTOINCREMENT, debate_id TEXT NOT NULL, seq INT, event_json TEXT NOT NULL, created_at TEXT)` con índice `(debate_id, seq)` (manteniendo lectura retrocompatible de `events_json` legado) para que `append_event` sea `INSERT` $O(1)$.
  3. Actualizar `backend/tests/infrastructure/persistence/test_sqlite_debate_repository.py` y `test_sqlite_user_repository.py` y verificar con `pytest`.

---

### [P2] God Modules (`supervisor_agent.py`, `ws/debate.py`), alta complejidad ciclomática y `except Exception: pass` silenciosos
- **Impacto:** Clean Code | Arquitectura
- **Target File(s):** `backend/src/application/agents/supervisor_agent.py` (1,331 líneas; `classify_intent` CC=17, `_build_role_runner` CC=14, `_run_phase_1` CC=14, `_run_phase_2` CC=12), `backend/src/presentation/api/ws/debate.py` (956 líneas; `_handle_pending_learning` CC=13, `_handle_learning` CC=10, `_init_session_and_trace` CC=10), `backend/src/infrastructure/rag/in_memory_document_store.py` (`_apply_filter` CC=23), `backend/src/application/services/vault_domain_service.py` (`create_domain` CC=16), `backend/src/application/services/auth_service.py` (L84, L313), `backend/src/infrastructure/audio/local_audio_service.py` (L14-L20, L71-L116), `backend/src/infrastructure/audio/wake_word_service.py` (L120-L145)
- **Current State (Problema):**
  1. `supervisor_agent.py` (1,331 líneas) agrupa triaje, prompts gigantes, state container, streaming bridge de threads, lógica HITL y 4 fases. Además `_run_phase_1`, `_run_phase_2` y `_run_phase_3` repiten el mismo bucle `while True: execute -> emit HITL -> await callback -> RETRY/HITL` y los bloques `_process_phase_{1,2,3}_hitl` duplican decisiones `FINISH`, `CONSOLIDATE`, `APPROVE`, `DIVERT`, `REFINE`.
  2. `ws/debate.py` (956 líneas) mezcla parsing regex de etiquetas/dominios en español, despacho de aprendizaje pendiente/activo, gestión de sesiones/IDOR, instrumentación Langfuse y ciclo de vida WebSocket.
  3. `in_memory_document_store.py:_apply_filter` (CC=23) repite `if filter.<field> is not None:` 6 veces en lugar de iterar sobre una tabla de campos.
  4. `auth_service.py` (L84, L313), `ws/debate.py` (L293, L323, L333, L583, L872, L882), `local_audio_service.py` (L125) y `wake_word.py` (L52, L119) usan `except Exception: pass`, ocultando fallos reales de persistencia o audio.
  5. `local_audio_service.py` hace monkey-patch global de `av.open` al importar el módulo y carga modelos lazy (`_get_whisper_model`, `_get_kokoro`) sin `threading.Lock`, causando doble carga en CPU ante peticiones concurrentes en frío.
- **Desired Outcome (Objetivo):** Módulos cohesivos bajo principio de Responsabilidad Única (SRP), eliminación de código duplicado en fases HITL, logging explícito de excepciones y locks en inicializaciones perezosas de modelos ML.
- **Actionable Steps for Agent:**
  1. Extraer de `supervisor_agent.py`: `triage_service.py` (`classify_intent`), `consolidation_service.py` y un helper genérico `_run_hitl_phase_loop(...)` parametrizado que unifique la mecánica común de fases 1, 2 y 3 sin duplicación.
  2. Extraer de `ws/debate.py` el parsing de aprendizaje (`learning_command_parser.py`) y el adaptador de observabilidad de eventos (`DebateObservabilityTracker`), reduciendo `DebateWebSocketHandler` a coordinación de transporte WS.
  3. Refactorizar `in_memory_document_store._apply_filter` iterando sobre `("type", "layer", "status", "phase", "category", "domain")` con `getattr`.
  4. Reemplazar `except Exception: pass` en `auth_service.py` y `ws/debate.py` por `logger.warning(..., exc_info=True)` y añadir `threading.Lock` en `_get_whisper_model`, `_get_kokoro` y `WakeWordService._initialize_model`.
  5. Verificar toda la suite con `pytest`.

---

### [P2] Desviaciones frente a estándares corporativos (`obsidian_vault/01_enterprise_architecture/`)
- **Impacto:** Arquitectura | Seguridad
- **Target File(s):** `backend/src/presentation/api/app.py` (L125-L139), `backend/src/presentation/api/routes/health.py`, `backend/src/presentation/api/routes/auth.py`, `backend/src/presentation/api/routes/config.py` (L183-L199), `backend/src/presentation/api/config.py` (L91-L93), `backend/src/infrastructure/audio/local_audio_service.py` (L73, L98, L110), `backend/src/infrastructure/audio/wake_word_service.py` (L133, L139, L163, L170, L177)
- **Current State (Problema):**
  Contrastando la implementación real contra `obsidian_vault/01_enterprise_architecture/`:
  1. **`api_design_standard.md`:** Las rutas no están versionadas bajo `/api/v1/` (están montadas en `/` y solo `auth.router` está duplicado en `/api` junto a `/api/images/{filename}`); `POST /auth/users` devuelve `200` en lugar de `201 Created`; y los errores devuelven `{"detail": "..."}` en lugar del sobre estándar `{"error": {"code": ..., "message": ..., "details": {}}}`. Además `GET /config/topology` (L183) carece de `Depends(get_current_user)` mientras el resto de `/config/*` sí lo exige.
  2. **`microservices_blueprint.md`:** Solo existe `GET /health` estático (`{"status": "ok"}`); faltan los probes diferenciados `/health/live` y `/health/ready` que comprueben conectividad con BD y ChromaDB, y falta drenado elegante de WebSockets activos en `SIGTERM`.
  3. **`observability_standards.md`:** Aunque `opentelemetry-*` figura en dependencias, no existe instrumentación OpenTelemetry ni propagación de `traceparent`/`x-trace-id` entre frontend, endpoints HTTP y LLMs; las rutas HTTP (`/learning/session`, `/audio/*`) no emiten trazas, y `local_audio_service.py` / `wake_word_service.py` usan `print()` desestructurado en lugar de logs JSON estructurados.
  4. **`security_and_identity.md`:** `Settings` establece por defecto `auth_cookie_secure=False` y `auth_cookie_samesite="lax"` (el estándar exige `Secure; SameSite=Strict` en producción); no existe anonimización/filtrado PII previo al envío de documentos/prompts a LLMs externos.
- **Desired Outcome (Objetivo):** Plan progresivo de alineación con las guías corporativas de API, probes Kubernetes, telemetría OTel/JSON logging y endurecimiento de cookies/PII.
- **Actionable Steps for Agent:**
  1. Añadir `/health/live` y `/health/ready` en `routes/health.py` (verificando acceso a BD y ChromaDB en `ready`), y proteger `GET /config/topology` con `Depends(get_current_user)` (o documentar explícitamente si `LoginView`/`SetupView` necesitan solo metadatos públicos mínimos vía `/auth/status`).
  2. Reemplazar los 8 `print(...)` de `local_audio_service.py` y `wake_word_service.py` por `logger.info(...)` y configurar un formatter JSON configurable por entorno (`LOG_FORMAT=json`) en `app.py` con middleware de correlación `X-Trace-Id`.
  3. Introducir un manejador global de excepciones (`@app.exception_handler`) o adaptador de errores compatible hacia el estándar `{"error": {"code", "message", "details"}}` y versionado `/api/v1/` coordinado con Nginx y Frontend.
  4. Validar con `pytest tests/presentation/api/`.

