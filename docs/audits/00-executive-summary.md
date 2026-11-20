# Auditoría Técnica `ai-agent-assistant` — Resumen Ejecutivo y Plan de Ejecución

Este índice consolida la auditoría estática integral del repositorio `ai-agent-assistant` (infraestructura, backend, frontend, contratos extremo a extremo, escalabilidad y limpieza), sin modificación alguna de código fuente o configuración.

Los hallazgos detallados con rutas, líneas exactas y pasos atómicos de remediación se distribuyen en cuatro reportes:
- [01-infrastructure-and-devops.md](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/docs/audits/01-infrastructure-and-devops.md) — **7 tickets** (`4 P1`, `3 P2`)
- [02-backend-clean-architecture.md](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/docs/audits/02-backend-clean-architecture.md) — **10 tickets** (`6 P1`, `4 P2`)
- [03-frontend-architecture.md](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/docs/audits/03-frontend-architecture.md) — **7 tickets** (`4 P1`, `2 P2`, `1 P3`)
- [04-integration-and-scalability.md](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/docs/audits/04-integration-and-scalability.md) — **7 tickets** (`5 P1`, `1 P2`, `1 P3`)

**Total:** 31 tickets accionables (`19 P1`, `10 P2`, `2 P3`).

---

## Diagnóstico Global por Área

| Área | Puntuación Inicial | Puntuación Actual (Fases 0–4) | Estado Actual | Resumen de Riesgos / Brechas Restantes |
| :--- | :---: | :---: | :--- | :--- |
| **1. Infraestructura y DevOps** (`01`) | 6.0 / 10 | **9.5 / 10** | Contenedores, Nginx, `.dockerignore`, caché ML, Trivy, paridad `.env.example`/Compose, CI (`ruff check .`) y `node:24-alpine` alineados | Solo diferencias esperadas de entorno host vs contenedor (`PYTHONUNBUFFERED`, `MALLOC_ARENA_MAX`, `LANGFUSE_BASE_URL`, `WHISPER_INITIAL_PROMPT` y extras `dev` en `.venv` local). |
| **2. Backend & Clean Architecture** (`02`) | 5.5 / 10 | **9.5 / 10** | `domain/` purificado, puertos hexagonales, async desbloqueado, `debate_events` $O(1)$, AST guards en estricto y `ruff check .` / `mypy src/` en cero errores | **Fase 5 (#31)** pendiente (`/api/v1/`, `/health/live` y `/health/ready`, sobre estándar de errores, OTel/logs JSON, cookies `Secure; SameSite=Strict`, saneamiento PII). |
| **3. Arquitectura Frontend** (`03`) | 5.5 / 10 | **9.5 / 10** | Capa `services/`, `ChatPanel` y `stores/debate.ts` descompuestos, `DOMPurify` + Mermaid `strict`, `tsconfig.e2e.json` activo y `pptxgenjs` diferido (`index` 549 kB) | Avisos de chunks > 500 kB en `vite build` (`elk`, `chunk-NGNAAXSQ`, `index`); re-sincronización WS tras reconexión ligada a Fase 5 (#30). |
| **4. Integración y Escalabilidad** (`04`) | 4.5 / 10 | **7.5 / 10** | Contratos REST/WS, HITL, tokens y paginación `/debates` corregidos para nodo único; E2E 38/38 y `tsconfig.e2e.json` en verde | **Fase 5 (#29 y #30)** pendiente para producción multi-réplica: estado mutable local (`wake_word_service`, HITL/cancelación en memoria, `Langfuse` compartido, rate limit sin Redis), falta de `asyncpg`/adaptadores Postgres y `ObjectStoragePort` (S3/MinIO). |

---

## ✅ Lo que está bien hecho (Fortalezas a Preservar)

Durante el plan de refactorización **no deben romperse ni degradarse** las siguientes piezas y decisiones ya consolidadas:

1. **Seguridad criptográfica y flujos de identidad (`backend/src/infrastructure/security/`, `auth_service.py`):**
   - `Argon2idPasswordHasher` (parámetros OWASP, protección DoS `MAX_PASSWORD_LENGTH = 128`, rechazo de null-bytes).
   - `JwtTokenService` (validación fail-fast de clave >= 32 bytes, rechazo de secretos conocidos, validación de `iss`, `aud` y `token_version`).
   - `AuthService`: hashing en `asyncio.to_thread`, `_DUMMY_HASH` contra enumeración por timing, `asyncio.Lock` en bootstrap e invariantes `LastAdminError` / `SelfModificationError`.
2. **Núcleo puro de dominio y caso de uso de referencia (`backend/src/domain/`, `run_agent_task.py`):**
   - Entidades/Value Objects (`Agent`, `User`, `DocumentChunk`, `SearchFilter` inmutable/hashable) y capa anticorrupción `exceptions.py`.
   - Caso de uso `RunAgentTask` completamente desacoplado de frameworks externos, con DTOs inmutables e inyección por constructor.
3. **Estrategias de resiliencia y guardas existentes:**
   - Patrón Stale-While-Revalidate + lock atómico en BD (`acquire_probe_lock`) y probing gratuito (`count_tokens`) en `routes/models.py`.
   - Serialización centralizada WebSocket en `presentation/api/ws/serializers.py`.
   - Guarda léxica en `test_decoupling_guard.py` (base a ampliar con reglas AST, sin debilitar las comprobaciones actuales).
4. **Higiene de tipos en Frontend y base de Contenedores:**
   - Cero `any`, `@ts-ignore`, `@ts-expect-error` o `eslint-disable` en `frontend/src` (excl. tests) y `"noUncheckedIndexedAccess": true` en `tsconfig.app.json`.
   - `frontend/Dockerfile` multi-stage (`node:20-alpine` -> `nginxinc/nginx-unprivileged:alpine` UID 101, `npm ci --ignore-scripts`).
   - Endurecimiento base de `docker-compose.yml` (`no-new-privileges:true`, límites de memoria, bind por defecto a `127.0.0.1`, red `data-net` marcada `internal: true`, ausencia de montaje de `/var/run/docker.sock`, pinning por SHA en `docker-publish.yml`, `X-Robots-Tag` en `nginx.conf`).
   - Arranque con suites de mocking E2E (`frontend/e2e/helpers/mockBackend.ts`) y utilidades puras en `frontend/src/utils/`.

---

## Orden de Ejecución Recomendado (Roadmap de Menor a Mayor Riesgo)

Se recomienda ejecutar los refactors siguiendo estas **6 fases incrementales**, validando siempre las suites de tests (`pytest`, `npm run type-check`, `npm run test:unit`) al término de cada fase.

### Fase 0 — Higiene del repositorio, blindaje de tests y correcciones de riesgo nulo
1. ✅ `[x]` `[04][P3]` Limpieza de scripts de debug huérfanos (`backend/patch_tests.py`, `backend/test_kokoro_whisper.py`, `frontend/test_history*.js`), artefactos runtime (`:memory:.ses`, `*.db`, `.chroma/`, `*.egg-info/`) y wikilink roto en `MOC_Enterprise_Architecture.md`.
2. ✅ `[x]` `[02][P1]` Corrección de `test_composition_root.py` (`db_path=` -> `sqlite_db_path=`), actualización de firma `list_models(..., probe: bool = True)` en `tests/doubles.py` y ampliación de `test_decoupling_guard.py` con guardas AST (ya activas en modo estricto sin exenciones tras completar el punto 26 en Fase 4).
3. ✅ `[x]` `[01][P1]` Actualización de `frontend/.dockerignore` (excluir `.env*`, `e2e/`, reportes) y adición de `healthcheck` HTTP al servicio `frontend` en `docker-compose.yml`.

### Fase 1 — Seguridad crítica, bugs de contrato activos y fugas de memoria puntuales (Bajo Riesgo)
4. ✅ `[x]` `[02][P1]` Cierre de **Path Traversal** en `ws/debate.py` (`attachments` / `routes/upload.py` usando `settings.max_learn_file_mb` y `attachment_id` opaco) y protección **SSRF** en `URLExtractor`.
5. ✅ `[x]` `[03][P1]` Cambio de `DiagramModal.vue` a `securityLevel: 'strict'` + integración de `DOMPurify` en todos los `v-html` e `innerHTML`.
6. ✅ `[x]` `[01][P1]` Endurecimiento de `frontend/nginx.conf` (`client_max_body_size 55m`, cabeceras de seguridad, `gzip`, `Cache-Control` y timeouts `/api/` + `/ws/`).
7. ✅ `[x]` `[04][P1]` Corrección de contratos REST/WS rotos: esquema `/api/learning/session`, `ok: True` booleano en `/api/upload`, proxy `/ws` en `frontend/vite.config.ts`, `VITE_WS_URL` relativo por defecto y `LANGFUSE_DASHBOARD_URL` pública.
8. ✅ `[x]` `[04][P1]` Solución a la pérdida silenciosa de mensajes en **Fase 4**, eliminación del doble conteo de tokens/turnos (`AGENT_COMPLETED` + `DONE`) y actualización de eventos legacy en `HistoryView.vue` y `mockBackend.ts`.
9. ✅ `[x]` `[04][P1]` Corrección del bug de cancelación durante HITL (`{type: 'cancel'}` disparando `HITLDecision.APPROVE`) y acotación inicial de `attemptReconnect()`.
10. ✅ `[x]` `[03][P1]` Limpieza determinista en frontend: desuscripción de callbacks TTS en `onUnmounted`, `wakeWordWs.onclose = null` en `stopAutoListen()`, limpieza de `setTimeout`/RAF y eliminación de listeners de teclado duplicados en modales.

### Fase 2 — Infraestructura, CI/CD y Operación de Contenedores (Riesgo Bajo-Medio)
11. ✅ `[x]` `[01][P1]` Unificación de variables entre `.env.example`, `docker-compose.yml` y `Settings`, separación entre puerto host y puerto interno de `chroma-server` (`CHROMA_PORT=8000`) y eliminación de secretos hardcoded en Compose.
12. ✅ `[x]` `[01][P1]` Refactorización de `backend/Dockerfile` a **multi-stage build** (`builder` + `runtime` slim sin compiladores, sin `chown -R` duplicando `.venv`, y `.dockerignore` actualizado).
13. ✅ `[x]` `[01][P2]` Persistencia del caché de modelos ML (`atenea_ml_cache:/home/atenea/.cache`), fijación de tags `:latest` en Compose, retirada de `app-net` en `langfuse-web` y retirada de `DockerObservabilityManager` del ciclo `lifespan`/`atexit` de FastAPI.
14. ✅ `[x]` `[01][P2]` Alineación de `.github/workflows/ci.yml` (`uv`, misma versión Python 3.12+, `ruff`, `mypy`, `npm run lint` no mutante, `npm run build`) y encadenamiento de `docker-publish.yml` con escaneo Trivy.
15. ✅ `[x]` `[01][P2]` Actualización de `scripts/download_models.sh` (verificación SHA-256), `scripts/ingest_vault.py` y `scripts/start.sh`.

### Fase 3 — Rendimiento, Asincronía Real y Calidad Interna sin Ruptura de Arquitectura (Riesgo Medio)
16. ✅ `[x]` `[02][P1]` Desbloqueo del event loop `async` en backend: `ChromaDBDocumentStore` singleton en `app.state`, `asyncio.to_thread` en RAG, triage LLM, learning, Vosk, métricas del sistema y `SQLiteUserRepository`.
17. ✅ `[x]` `[02][P2]` Eliminación de la race condition en `self._last_usage` y round-trips redundantes en `GeminiAdapter`, más `Any` faltante y `complete_stream` en `AnthropicAdapter`.
18. ✅ `[x]` `[02][P2]` Migración de `SqliteDebateRepository.append_event` de $O(N^2)$ a tabla normalizada `debate_events` $O(1)$, helper `SqliteConnectionManager` con WAL y cierre garantizado de conexiones.
19. ✅ `[x]` `[03][P2]` Optimización de renderizado en Vue: pausa y optimización $O(n^2)$ en `ParticleOrb.vue`, montaje condicional único de `SoundBar`, gating de polling en `ObservabilityPanel.vue`, claves únicas estables y memoización en `ChatPanel.vue` / `EventStream.vue`.
20. ✅ `[x]` `[03][P2]` Consolidación de utilidades TTS en `ttsFilter.ts`, eliminación de listas hardcodeadas de agentes/dominios y CSS autocontenido offline en `presentationExporter.ts`.
21. ✅ `[x]` `[03][P3]` Debounce/`@change` en sliders de `AgentCard.vue`, simplificación de watchers en `ChatPanel.vue` y sustitución de métricas sintéticas de tokens/caché en `stores/debate.ts` por telemetría del backend.
22. ✅ `[x]` `[04][P2]` Paginación y proyección ligera en `GET /debates` (`DebateSummaryDTO`).

### Fase 4 — Refactor Estructural: Hexagonal Estricta y Desacoplamiento Frontend (Riesgo Medio-Alto)
23. ✅ `[x]` `[02][P1]` Purificación de `domain/`: extraer YAML, `os`, rutas y estado global mutable fuera de `sub_agent_profiles.py`, `debate_topology.py` y `task.py` hacia repositorios en `infrastructure/`.
24. ✅ `[x]` `[02][P1]` Inversión de dependencias desde `application/` e `infrastructure/` (`supervisor_agent.py`, `sub_agent_runner.py`, `ingest_vault.py`, `learn_from_source.py`, `registry.py`, `image_generation/service.py`) introduciendo puertos en `domain/ports/`.
25. ✅ `[x]` `[02][P1]` Consolidación de un único `LLMProviderRegistry` en el composition root, estandarización de `domain/ports/*` (`Protocol` vs `ABC`) y traslado de `NoOpObservabilityService` a `infrastructure/observability/`.
26. ✅ `[x]` `[02][P2]` Descomposición de God Modules (`supervisor_agent.py`, `ws/debate.py`), simplificación de `_apply_filter`, `threading.Lock` en modelos de audio y sustitución de `except Exception: pass` por logging explícito. *(Al finalizar los puntos 23-26, activar en verde estricto las guardas AST de `test_decoupling_guard.py`)*.
27. ✅ `[x]` `[03][P1]` Creación de la capa `frontend/src/services/` (`httpClient.ts`, servicios de API y WebSockets) y eliminación del monkey-patch global de `window.fetch` en `main.ts`.
28. ✅ `[x]` `[03][P1]` Descomposición de `ChatPanel.vue` (1959 L), `stores/debate.ts` (1693 L) y modales pesados en composables de audio/wake-word y subcomponentes presentacionales cohesionados.

### Fase 5 — Escalado Horizontal Stateless Multi-Réplica y Estándares Enterprise (Riesgo Alto)
29. `[04][P1]` Eliminación de estado mutable compartido en proceso: `KaldiRecognizer` aislado por conexión en `ws/wake_word.py`, `RedisRateLimiter` + corrección de `get_client_ip`, `AUTH_SECRET_KEY` obligatorio en producción, trazado sin diccionarios compartidos en `LangfuseObservabilityAdapter` y coordinación de sesiones HITL/cancelación mediante Redis Pub/Sub.
30. `[04][P1]` Persistencia distribuida completa para perfil `scale`: añadir `asyncpg` a `pyproject.toml`, implementar adaptadores PostgreSQL para `Debate`, `AgentConfig`, `ModelCache`, `Task` y `Agent`, extraer `ObjectStoragePort` (MinIO/S3) para adjuntos/imágenes y forzar `ChromaDBDocumentStore` con `HttpClient` (+ re-sincronización de estado tras reconexión WebSocket en cliente).
31. `[02][P2]` Convergencia con los estándares de `obsidian_vault/01_enterprise_architecture/`: versionado `/api/v1/`, sobre estándar de errores, probes `/health/live` y `/health/ready`, propagación `traceparent`/OpenTelemetry, logs JSON estructurados, cookies `Secure; SameSite=Strict` y saneamiento PII pre-LLM.

---

## Verificación Integral Post-Fases 0–4 y Corrección de Flecos Menores

Comprobación final ejecutada sobre la rama `refactor/architecture-audit` (base `cda3abd` + correcciones de flecos menores), sin añadir nuevas funcionalidades.

### Resultados de Verificación Estática, Tests y Contenedores

- **Backend:**
  - `ruff check .` (alcance completo `src` + `tests` de `backend/pyproject.toml`): **OK** — `All checks passed!` (`0` errores tras limpiar los 36 avisos heredados en `tests/`).
  - `mypy src/` (`uv run --no-sync --offline --with mypy mypy src/`): **OK** — `Success: no issues found in 122 source files` (`ignore_missing_imports = true`, `python_version = "3.12"` en `backend/pyproject.toml`).
  - `STRICT_ARCH_GUARD=1 pytest -v tests/application/agents/test_decoupling_guard.py tests/presentation/api/dependencies/test_composition_root.py`: **31 passed, 1 warning** en `2.74s` (guardas AST de arquitectura limpia y `STRICT_PROMPT_MODULES` en estricto con cero exenciones).
  - `STRICT_ARCH_GUARD=1 pytest -q`: **568 passed, 1 warning** en `131.93s` (`0:02:11`, solo un `DeprecationWarning` de terceros en `google/genai/types.py:42` bajo Python `3.14`).
- **Frontend:**
  - `npm run type-check` (`vue-tsc --build`, incluyendo `frontend/tsconfig.e2e.json`): **OK** (`0` errores).
  - `npm run lint` (`oxlint .` + `eslint . --cache`): **OK** — `0` warnings y `0` errores (`129` ficheros analizados por `oxlint`).
  - `npm run test:unit` (`vitest run`): **44 test files passed (44)**, **430 tests passed (430)** en `15.79s`.
  - `npm run build` (`vite build`): **OK** en `2.67s`; la carga diferida de `pptxgenjs` extrajo `pptxgen.es` (`368.44 kB`) del chunk inicial (`index`: `917.95 kB` -> `549.29 kB`), manteniéndose avisos informativos en chunks > 500 kB (`elk`, `chunk-NGNAAXSQ`, `index`).
  - `npx playwright test`: **38 passed** en `28.4s` (`chromium` + `mobile-chrome`); sin cambios requeridos en selectores ni mocks de UI.
- **Contenedores (`docker compose`):**
  - `docker compose config --quiet` (por defecto y con perfiles `local`, `scale`, `observability`, `full`): **OK** (`exit 0`).
  - `AUTH_SECRET_KEY=... docker compose --env-file .env.example --profile full config --quiet`: **OK** (`exit 0`, requiere definir `AUTH_SECRET_KEY` porque está comentada en `.env.example` para impedir secretos por defecto).
  - **Paridad `.env.example` / `docker-compose.yml`:** **0** sustituciones `${...}` de Compose ausentes en `.env.example` y **0** variables de `backend.environment` sin documentar salvo flags runtime del contenedor (`PYTHONUNBUFFERED`, `MALLOC_ARENA_MAX`).

### Flecos Menores Corregidos

1. **Higiene en `backend/tests/` y alcance de CI:** eliminados 36 errores de `ruff check .` en 24 ficheros de `tests/` (`27 F401`, `8 F841`, `1 E402` en `test_wake_word.py`) y actualizado `.github/workflows/ci.yml` de `ruff check src` a `ruff check .`.
2. **Paridad de configuración Docker/Env:** reenviadas en `docker-compose.yml` `TASK_PROMPT_MAX_LENGTH`, opciones de `WHISPER_*`/`KOKORO_*` (respetando `WHISPER_INITIAL_PROMPT` por defecto en `Settings`) y `LANGFUSE_DEFAULT_USER_ID`; documentadas en `.env.example` `VAULT_ROOT`, `IMAGE_GENERATION_PROVIDER`, bloque de audio, Langfuse y overrides opcionales de puertos/bind.
3. **Alineación Frontend / E2E / Docker:** actualizado `frontend/Dockerfile` de `node:20-alpine` a `node:24-alpine` (paridad con `package.json` `engines` y CI), añadido `frontend/tsconfig.e2e.json` en `frontend/tsconfig.json`, corregida normalización defensiva `d.events ?? []` en `frontend/e2e/helpers/mockBackend.ts` (6 errores latentes `TS18048`/`TS2488`) y pasada a carga dinámica `await import('pptxgenjs')` en `frontend/src/utils/presentationExporter.ts`.

### Elementos Pendientes

1. **Detalles menores no bloqueantes:**
   - El `.venv` local de `backend/` corre Python `3.14` y no tenía sincronizado `--extra dev` (`ruff`, `mypy`, solo `pytest`).
   - Valorar code-splitting adicional para diagramas Mermaid si se quieren eliminar los avisos de chunks > 500 kB (`elk`, `chunk-NGNAAXSQ`, `index`).
   - En `docker-compose.yml` se omiten intencionadamente `API_VERSION` (constante de release), `LANGFUSE_BASE_URL` (alias host frente a DNS interno `langfuse-web`) y `WHISPER_INITIAL_PROMPT` (para no sobreescribir el prompt técnico por defecto con cadena vacía).
2. **Bloques mayores de Fase 5 (sin iniciar):**
   - Puntos **29**, **30** y **31** del roadmap (estado stateless multi-réplica, adaptadores Postgres + `asyncpg` + `ObjectStoragePort` + ChromaDB `HttpClient`, y estándares enterprise `/api/v1/`, probes `/health/live` y `/health/ready`, OTel/logs JSON, cookies `Secure; SameSite=Strict` y saneamiento PII pre-LLM).

