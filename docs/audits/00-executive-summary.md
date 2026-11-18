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

| Área | Puntuación | Estado Actual | Resumen de Riesgos Principales |
| :--- | :---: | :--- | :--- |
| **1. Infraestructura y DevOps** (`01`) | **6.0 / 10** | Base Compose sólida, brechas en Dockerfile backend, Nginx, `.env` y CI | `backend/Dockerfile` single-stage con `chown -R` que duplica capas; Nginx sin `client_max_body_size` (bloquea >1 MB); colisión `CHROMA_PORT` y desfase `.env.example`/Compose; `frontend/.dockerignore` sin `.env*`; CI en Python `3.14` sin `ruff`/`mypy`/build. |
| **2. Backend & Clean Architecture** (`02`) | **5.5 / 10** | Núcleo de auth/casos de uso robusto, Regla de Dependencia y loop `async` comprometidos en agentes | `domain/agents/` importa `PyYAML`/`os` y lee disco al importar; `application/` e `infrastructure/` importan `presentation/api/config.py`; event loop bloqueado en RAG, triage, learning y SQLite; Path Traversal en `attachments` + SSRF en `URLExtractor`; `test_composition_root.py` usa argumento descartado `db_path=`. |
| **3. Arquitectura Frontend** (`03`) | **5.5 / 10** | TypeScript estricto impecable, pero monolitos, fugas de ciclo de vida y sin capa de servicios | `DiagramModal` usa `securityLevel: 'loose'` sin `DOMPurify`; `ChatPanel.vue` (1959 L) y `stores/debate.ts` (1693 L) monolíticos; monkey-patch de `window.fetch` y llamadas `fetch` dispersas; fugas en callbacks TTS y doble keydown en modales; bucle $O(n^2)$ en `ParticleOrb` y doble `SoundBar` activo. |
| **4. Integración y Escalabilidad** (`04`) | **4.5 / 10** | Operativo en nodo único con bugs de contrato; bloqueado para multi-réplica | Mensajes de Fase 4 silenciados y doble conteo de tokens; `POST /api/learning/session` desalineado; `{type: 'cancel'}` durante HITL dispara `APPROVE`; `asyncpg` ausente y Postgres solo implementado para `User`; `wake_word_service` compartido entre usuarios y estado mutable local al proceso. |

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
1. `[04][P3]` Limpieza de scripts de debug huérfanos (`backend/patch_tests.py`, `backend/test_kokoro_whisper.py`, `frontend/test_history*.js`), artefactos runtime (`:memory:.ses`, `*.db`, `.chroma/`, `*.egg-info/`) y wikilink roto en `MOC_Enterprise_Architecture.md`.
2. `[02][P1]` Corrección de `test_composition_root.py` (`db_path=` -> `sqlite_db_path=`), actualización de firma `list_models(..., probe: bool = True)` en `tests/doubles.py` y ampliación de `test_decoupling_guard.py` con guardas AST (ejecutar inicialmente como aviso/baseline hasta completar la Fase 4).
3. `[01][P1]` Actualización de `frontend/.dockerignore` (excluir `.env*`, `e2e/`, reportes) y adición de `healthcheck` HTTP al servicio `frontend` en `docker-compose.yml`.

### Fase 1 — Seguridad crítica, bugs de contrato activos y fugas de memoria puntuales (Bajo Riesgo)
4. `[02][P1]` Cierre de **Path Traversal** en `ws/debate.py` (`attachments` / `routes/upload.py` usando `settings.max_learn_file_mb` y `attachment_id` opaco) y protección **SSRF** en `URLExtractor`.
5. `[03][P1]` Cambio de `DiagramModal.vue` a `securityLevel: 'strict'` + integración de `DOMPurify` en todos los `v-html` e `innerHTML`.
6. `[01][P1]` Endurecimiento de `frontend/nginx.conf` (`client_max_body_size 55m`, cabeceras de seguridad, `gzip`, `Cache-Control` y timeouts `/api/` + `/ws/`).
7. `[04][P1]` Corrección de contratos REST/WS rotos: esquema `/api/learning/session`, `ok: True` booleano en `/api/upload`, proxy `/ws` en `frontend/vite.config.ts`, `VITE_WS_URL` relativo por defecto y `LANGFUSE_DASHBOARD_URL` pública.
8. `[04][P1]` Solución a la pérdida silenciosa de mensajes en **Fase 4**, eliminación del doble conteo de tokens/turnos (`AGENT_COMPLETED` + `DONE`) y actualización de eventos legacy en `HistoryView.vue` y `mockBackend.ts`.
9. `[04][P1]` Corrección del bug de cancelación durante HITL (`{type: 'cancel'}` disparando `HITLDecision.APPROVE`) y acotación inicial de `attemptReconnect()`.
10. `[03][P1]` Limpieza determinista en frontend: desuscripción de callbacks TTS en `onUnmounted`, `wakeWordWs.onclose = null` en `stopAutoListen()`, limpieza de `setTimeout`/RAF y eliminación de listeners de teclado duplicados en modales.

### Fase 2 — Infraestructura, CI/CD y Operación de Contenedores (Riesgo Bajo-Medio)
11. `[01][P1]` Unificación de variables entre `.env.example`, `docker-compose.yml` y `Settings`, separación entre puerto host y puerto interno de `chroma-server` (`CHROMA_PORT=8000`) y eliminación de secretos hardcoded en Compose.
12. `[01][P1]` Refactorización de `backend/Dockerfile` a **multi-stage build** (`builder` + `runtime` slim sin compiladores, sin `chown -R` duplicando `.venv`, y `.dockerignore` actualizado).
13. `[01][P2]` Persistencia del caché de modelos ML (`atenea_ml_cache:/home/atenea/.cache`), fijación de tags `:latest` en Compose, retirada de `app-net` en `langfuse-web` y retirada de `DockerObservabilityManager` del ciclo `lifespan`/`atexit` de FastAPI.
14. `[01][P2]` Alineación de `.github/workflows/ci.yml` (`uv`, misma versión Python 3.12+, `ruff`, `mypy`, `npm run lint` no mutante, `npm run build`) y encadenamiento de `docker-publish.yml` con escaneo Trivy.
15. `[01][P2]` Actualización de `scripts/download_models.sh` (verificación SHA-256), `scripts/ingest_vault.py` y `scripts/start.sh`.

### Fase 3 — Rendimiento, Asincronía Real y Calidad Interna sin Ruptura de Arquitectura (Riesgo Medio)
16. `[02][P1]` Desbloqueo del event loop `async` en backend: `ChromaDBDocumentStore` singleton en `app.state`, `asyncio.to_thread` en RAG, triage LLM, learning, Vosk, métricas del sistema y `SQLiteUserRepository`.
17. `[02][P2]` Eliminación de la race condition en `self._last_usage` y round-trips redundantes en `GeminiAdapter`, más `Any` faltante y `complete_stream` en `AnthropicAdapter`.
18. `[02][P2]` Migración de `SqliteDebateRepository.append_event` de $O(N^2)$ a tabla normalizada `debate_events` $O(1)$, helper `SqliteConnectionManager` con WAL y cierre garantizado de conexiones.
19. `[03][P2]` Optimización de renderizado en Vue: pausa y optimización $O(n^2)$ en `ParticleOrb.vue`, montaje condicional único de `SoundBar`, gating de polling en `ObservabilityPanel.vue`, claves únicas estables y memoización en `ChatPanel.vue` / `EventStream.vue`.
20. `[03][P2]` Consolidación de utilidades TTS en `ttsFilter.ts`, eliminación de listas hardcodeadas de agentes/dominios y CSS autocontenido offline en `presentationExporter.ts`.
21. `[03][P3]` Debounce/`@change` en sliders de `AgentCard.vue`, simplificación de watchers en `ChatPanel.vue` y sustitución de métricas sintéticas de tokens/caché en `stores/debate.ts` por telemetría del backend.
22. `[04][P2]` Paginación y proyección ligera en `GET /debates` (`DebateSummaryDTO`).

### Fase 4 — Refactor Estructural: Hexagonal Estricta y Desacoplamiento Frontend (Riesgo Medio-Alto)
23. `[02][P1]` Purificación de `domain/`: extraer YAML, `os`, rutas y estado global mutable fuera de `sub_agent_profiles.py`, `debate_topology.py` y `task.py` hacia repositorios en `infrastructure/`.
24. `[02][P1]` Inversión de dependencias desde `application/` e `infrastructure/` (`supervisor_agent.py`, `sub_agent_runner.py`, `ingest_vault.py`, `learn_from_source.py`, `registry.py`, `image_generation/service.py`) introduciendo puertos en `domain/ports/`.
25. `[02][P1]` Consolidación de un único `LLMProviderRegistry` en el composition root, estandarización de `domain/ports/*` (`Protocol` vs `ABC`) y traslado de `NoOpObservabilityService` a `infrastructure/observability/`.
26. `[02][P2]` Descomposición de God Modules (`supervisor_agent.py`, `ws/debate.py`), simplificación de `_apply_filter`, `threading.Lock` en modelos de audio y sustitución de `except Exception: pass` por logging explícito. *(Al finalizar los puntos 23-26, activar en verde estricto las guardas AST de `test_decoupling_guard.py`)*.
27. `[03][P1]` Creación de la capa `frontend/src/services/` (`httpClient.ts`, servicios de API y WebSockets) y eliminación del monkey-patch global de `window.fetch` en `main.ts`.
28. `[03][P1]` Descomposición de `ChatPanel.vue` (1959 L), `stores/debate.ts` (1693 L) y modales pesados en composables de audio/wake-word y subcomponentes presentacionales cohesionados.

### Fase 5 — Escalado Horizontal Stateless Multi-Réplica y Estándares Enterprise (Riesgo Alto)
29. `[04][P1]` Eliminación de estado mutable compartido en proceso: `KaldiRecognizer` aislado por conexión en `ws/wake_word.py`, `RedisRateLimiter` + corrección de `get_client_ip`, `AUTH_SECRET_KEY` obligatorio en producción, trazado sin diccionarios compartidos en `LangfuseObservabilityAdapter` y coordinación de sesiones HITL/cancelación mediante Redis Pub/Sub.
30. `[04][P1]` Persistencia distribuida completa para perfil `scale`: añadir `asyncpg` a `pyproject.toml`, implementar adaptadores PostgreSQL para `Debate`, `AgentConfig`, `ModelCache`, `Task` y `Agent`, extraer `ObjectStoragePort` (MinIO/S3) para adjuntos/imágenes y forzar `ChromaDBDocumentStore` con `HttpClient` (+ re-sincronización de estado tras reconexión WebSocket en cliente).
31. `[02][P2]` Convergencia con los estándares de `obsidian_vault/01_enterprise_architecture/`: versionado `/api/v1/`, sobre estándar de errores, probes `/health/live` y `/health/ready`, propagación `traceparent`/OpenTelemetry, logs JSON estructurados, cookies `Secure; SameSite=Strict` y saneamiento PII pre-LLM.

