# Auditoría 01 — Infraestructura, Contenedores y DevOps

## ✅ Lo que está bien hecho

- **Frontend Multi-Stage y Non-Root (`frontend/Dockerfile`):** El build de frontend utiliza correctamente dos etapas (`node:20-alpine` como `builder` y `nginxinc/nginx-unprivileged:alpine` en runtime), instala dependencias de forma determinista con `npm ci --ignore-scripts` aprovechando caché de capa en `package*.json`, y ejecuta Nginx como usuario sin privilegios (UID `101`) escuchando en el puerto `8080`.
- **Endurecimiento de contenedores y límites de recursos (`docker-compose.yml`):** Todos los servicios declaran `security_opt: [no-new-privileges:true]` y `deploy.resources.limits.memory`, además de publicar puertos vinculados por defecto a `127.0.0.1` (`${*_BIND_IP:-127.0.0.1}`) evitando exposición involuntaria en `0.0.0.0`.
- **Aislamiento de red de datos y perfiles Compose (`docker-compose.yml`):** La red `data-net` está marcada como `internal: true`, aislando `postgres`, `redis`, `chroma-server`, `clickhouse`, `minio` y `langfuse-worker` de tráfico saliente hacia Internet, mientras `backend` hace de puente hacia `app-net` (para llamadas a LLMs externos). Los perfiles (`local`, `scale`, `observability`, `full`) permiten adaptar el despliegue sin duplicar archivos Compose.
- **Healthchecks y arranque ordenado en servicios clave (`docker-compose.yml`):** `backend`, `chroma-server`, `postgres`, `redis`, `langfuse-web`, `clickhouse` y `minio` tienen `healthcheck` definidos, y `frontend` y `langfuse-*` usan `depends_on` con `condition: service_healthy`.
- **Ausencia de montaje de Docker Socket en el contenedor backend:** `docker-compose.yml` **no** monta `/var/run/docker.sock` en `atenea-backend`, evitando el vector de escalada de privilegios equivalente a `root` en el host.
- **Pinning y permisos mínimos en publicación de imágenes (`.github/workflows/docker-publish.yml`):** Las GitHub Actions de terceros están fijadas por SHA de commit y los permisos del workflow se limitan a `contents: read` y `packages: write`, con caché de Buildx en GHA separada por `scope=backend` y `scope=frontend`.
- **Cabecera anti-indexación en Nginx (`frontend/nginx.conf`):** Se aplica `X-Robots-Tag "noindex, nofollow, noarchive, nosnippet, noimageindex" always;` en el servidor web.

---

### [P1] Imagen backend single-stage con `build-essential` en runtime y duplicación de capas por `chown -R`
- **Impacto:** Rendimiento | Seguridad
- **Target File(s):** `backend/Dockerfile` (L1-L45), `backend/.dockerignore` (L1-L10)
- **Current State (Problema):**
  1. `backend/Dockerfile` utiliza una única etapa sobre `python:3.11-slim` instalando `build-essential` (gcc, g++, make, cabeceras libc) en L6-L10 y dejándolo en la imagen final, aumentando la superficie de ataque y el tamaño de imagen (además de mantener los binarios `uv`/`uvx` en `/bin/`).
  2. En L26 se ejecuta `uv sync --frozen --no-install-project --no-dev --no-cache` como `root` (creando `/app/.venv` con PyTorch, `sentence-transformers`, `faster-whisper`, `chromadb`, etc.), pero en L33 se ejecuta `RUN chown -R atenea:atenea /app`. En OverlayFS, cambiar recursivamente el propietario de todo `.venv` en una capa posterior duplica íntegramente los cientos de MB/GB de dependencias en la imagen final.
  3. En L30 se vuelven a copiar `pyproject.toml` y `uv.lock` (ya copiados en L23) junto a `requirements.txt`.
  4. `backend/.dockerignore` no excluye `*.egg-info/` (copia `src/ai_agent_assistant_backend.egg-info/`), `.env*`, `*.ses` ni scripts sueltos (`patch_tests.py`, `test_kokoro_whisper.py`), y el modelo Vosk (`backend/src/infrastructure/models/vosk/vosk-model-small-es-0.42/`, ~40 MB) vive dentro de `src/`, quedando embebido en cada reconstrucción de código fuente en lugar de separarse en una capa previa o volumen como `voices/`.
- **Desired Outcome (Objetivo):** Dockerfile multi-stage (`builder` + `runtime` slim sin compiladores), con creación de `.venv` ya bajo el usuario `atenea` (o `COPY --from=builder --chown=atenea:atenea /app/.venv /app/.venv` sin `chown -R` posterior), separación de modelos estáticos en una capa cacheable previa a `src/`, y `.dockerignore` completo.
- **Actionable Steps for Agent:**
  1. Refactorizar `backend/Dockerfile` en dos etapas: etapa `builder` (`python:3.11-slim`) con `build-essential`, `uv`, `COPY pyproject.toml uv.lock ./` y `uv sync --frozen --no-install-project --no-dev --no-cache`; etapa `runtime` (`python:3.11-slim`) con únicamente librerías de runtime (`curl`, `libsndfile1`), usuario `atenea` (`UID 1000`), y `COPY --from=builder --chown=atenea:atenea /app/.venv /app/.venv`.
  2. Copiar el modelo Vosk (o descargarlo/montarlo en `/app/models/vosk-model-small-es-0.42` fuera de `src/` y fijar `VOSK_MODEL_PATH`) en una capa anterior a `COPY --chown=atenea:atenea src/ /app/src/` para no invalidar la caché de 40 MB en cada cambio de código.
  3. Eliminar `RUN chown -R atenea:atenea /app` sobre `.venv` y evitar re-copiar `pyproject.toml`, `uv.lock` y `requirements.txt` si el runtime no los requiere.
  4. Actualizar `backend/.dockerignore` añadiendo `*.egg-info/`, `.env*`, `*.ses`, `voices/`, `patch_tests.py`, `test_kokoro_whisper.py` y `src/infrastructure/models/` (si se monta por volumen) o `*.DS_Store`.
  5. Verificar construyendo la imagen con `docker build -t atenea-backend:audit ./backend`, comprobando usuario (`docker run --rm atenea-backend:audit id`), ausencia de `gcc` y reducción del tamaño final con `docker images` y `docker history`.

---

### [P1] Nginx carece de `client_max_body_size`, cabeceras de seguridad, compresión y caché de estáticos
- **Impacto:** Seguridad | Rendimiento
- **Target File(s):** `frontend/nginx.conf` (L1-L34)
- **Current State (Problema):**
  1. **Bloqueo de subidas > 1 MB:** `frontend/nginx.conf` no define `client_max_body_size`. El valor por defecto de Nginx es `1m`, por lo que cualquier subida de PDF o imagen superior a 1 MB hacia `POST /api/upload` (cuyo límite en backend es `MAX_LEARN_FILE_MB=50`) falla en el proxy con `413 Request Entity Too Large`.
  2. **Cabeceras de seguridad ausentes:** Faltan `server_tokens off;`, `X-Content-Type-Options "nosniff"`, `X-Frame-Options "SAMEORIGIN"` (o `Content-Security-Policy` con `frame-ancestors 'self'`), `Referrer-Policy "strict-origin-when-cross-origin"` y `Permissions-Policy`.
  3. **Sin compresión ni políticas de caché:** No hay `gzip` habilitado para bundles JS/CSS ni distinción de `Cache-Control` entre `index.html` (`no-store, no-cache`) y los assets versionados con hash de Vite en `/assets/` (`public, max-age=31536000, immutable`).
  4. **Proxy `/ws/` y `/api/` incompletos:** `location /ws/` omite `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` y `proxy_send_timeout 86400`. `location /api/` usa el `proxy_read_timeout` por defecto (60 s), insuficiente para `POST /api/learning/session` que invoca al LLM + re-ingesta síncrona del Vault.
- **Desired Outcome (Objetivo):** Configuración Nginx endurecida y optimizada para SPA + proxy REST/WebSocket con límites de cuerpo acordes al backend, compresión gzip, caché inmutable para estáticos y timeouts adecuados.
- **Actionable Steps for Agent:**
  1. Añadir `server_tokens off;`, `client_max_body_size 55m;` y cabeceras de seguridad (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` recordando `microphone=(self)` para Web Audio / Wake-Word) en `frontend/nginx.conf`.
  2. Configurar `gzip on;` con tipos `text/css application/javascript application/json image/svg+xml` y añadir bloques `location = /index.html` (`Cache-Control "no-cache"`) y `location /assets/` (`Cache-Control "public, max-age=31536000, immutable"`).
  3. Añadir `proxy_set_header X-Real-IP $remote_addr;`, `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`, `proxy_set_header X-Forwarded-Proto $scheme;` y `proxy_send_timeout 86400;` en `location /ws/`, además de `proxy_read_timeout 180s;` en `location /api/`.
  4. Validar sintaxis ejecutando `docker build -t atenea-frontend:audit ./frontend` y `docker run --rm atenea-frontend:audit nginx -t`.

---

### [P1] Desalineación de variables de entorno, colisión de puertos y secretos por defecto en Compose
- **Impacto:** Arquitectura | Seguridad
- **Target File(s):** `docker-compose.yml` (L41-L70, L106-L115, L220-L350), `.env.example` (L16-L162), `backend/src/presentation/api/config.py` (L43-L109), `backend/src/infrastructure/rag/chroma_document_store.py` (L55-L62)
- **Current State (Problema):**
  1. **Nombres divergentes de variables:** `docker-compose.yml` (L70) pasa `DATABASE_URL=${AUTH_DATABASE_URL:-}`, mientras `.env.example` (L147) documenta `DATABASE_URL=...`; si el usuario configura `DATABASE_URL` en `.env`, Compose la ignora. Igualmente `.env.example` documenta `DB_PATH` (L18) y `CHROMA_PATH` (L26), pero `Settings` en `config.py` lee `SQLITE_DB_PATH` y `CHROMA_PERSIST_DIR`, mientras `ChromaDBDocumentStore` (L61) aún lee `CHROMA_PATH`.
  2. **Colisión de `CHROMA_PORT`:** `chroma-server` (L114) publica `${CHROMA_PORT:-8001}:8000` en el host, pero `backend` (L45) inyecta `CHROMA_PORT=${CHROMA_PORT:-8000}` para conectarse internamente a `chroma-server` por `data-net`. Si se define `CHROMA_PORT=8001` para evitar conflicto con el puerto `8000` del backend en el host, el backend intenta conectar a `chroma-server:8001` cuando Chroma escucha en el puerto `8000` del contenedor.
  3. **Modelos y URLs inconsistentes:** `.env.example` (L58) define `DEFAULT_MODEL=gemini-1.5-flash` y `docker-compose.yml` (L50) usa `gemini-3.6-flash`. Además `docker-compose.yml` (L53) fija `LANGFUSE_HOST=http://langfuse-web:3000` y no pasa `LANGFUSE_DASHBOARD_URL` al backend, causando que `/observability/stats` devuelva `http://langfuse-web:3000` (inaccesible desde el navegador del usuario).
  4. **Secretos criptográficos por defecto hardcoded en Compose:** `langfuse-web` y `langfuse-worker` (L224-L243, L280-L298) y `minio`/`postgres`/`clickhouse` tienen fallbacks literales inseguros (`atenea_super_secret_nextauth_token_32bytes_sample`, `0123456789abcdef...`, `miniosecret`, `postgres`, `clickhouse`). Adicionalmente `backend` no fuerza error si `AUTH_SECRET_KEY` está vacío en entorno Compose, haciendo que `config.py` genere una clave aleatoria volátil por proceso.
- **Desired Outcome (Objetivo):** Contrato único de variables de entorno entre `.env.example`, `docker-compose.yml` y `Settings`, separación entre puerto de host y puerto interno de ChromaDB, y fallo rápido ante secretos faltantes en producción.
- **Actionable Steps for Agent:**
  1. Unificar en `docker-compose.yml` y `.env.example`: usar `DATABASE_URL=${DATABASE_URL:-}`, eliminar referencias obsoletas a `DB_PATH`/`CHROMA_PATH` (o soportar alias explícitos en `Settings`), alinear `DEFAULT_MODEL`, y propagar `LANGFUSE_DASHBOARD_URL=${LANGFUSE_DASHBOARD_URL:-http://localhost:3000}`.
  2. Separar el mapeo de puerto host de Chroma (`${CHROMA_HOST_PORT:-8001}:8000`) de la variable interna del backend (`CHROMA_PORT=8000`).
  3. Requerir variables críticas en perfiles de producción/observabilidad (`${NEXTAUTH_SECRET:?...}`, `${AUTH_SECRET_KEY:?...}` o perfil explícito `dev` vs `prod`) eliminando claves criptográficas hardcoded de ejemplo en `docker-compose.yml`.
  4. Verificar configuración renderizada con `docker compose --profile full config` y tests de `Settings` en `backend/tests/presentation/api/test_app.py`.

---

### [P1] Exclusiones incompletas en `frontend/.dockerignore` (riesgo de fuga `.env`) y falta de `healthcheck` en `frontend`
- **Impacto:** Seguridad | Rendimiento
- **Target File(s):** `frontend/.dockerignore` (L1-L6), `docker-compose.yml` (L82-L102)
- **Current State (Problema):**
  1. `frontend/.dockerignore` solo excluye `node_modules/`, `dist/`, `coverage/`, `.eslintcache`, `.vscode/` y `.DS_Store`. No excluye `.env`, `.env.*`, `e2e/`, `playwright-report/`, `test-results/`, `src/**/__tests__/` ni `test_history*.js`. Esto invalida la caché de `COPY . .` ante cambios en tests E2E y permite que un `frontend/.env` local (con `VITE_WS_URL=ws://localhost:8000/ws/debate`) quede compilado dentro del bundle estático de producción.
  2. El servicio `frontend` en `docker-compose.yml` (L82-L102) carece de bloque `healthcheck`, impidiendo que un proxy inverso (NPM) o `docker compose ps` conozca si Nginx está listo y sirviendo tráfico en `:8080`.
- **Desired Outcome (Objetivo):** Contexto de build frontend mínimo y libre de secretos locales, más healthcheck HTTP nativo en el contenedor Nginx.
- **Actionable Steps for Agent:**
  1. Añadir `.env`, `.env.*`, `!.env.example`, `e2e/`, `playwright-report/`, `test-results/`, `test_history*.js`, `*.tsbuildinfo` a `frontend/.dockerignore`.
  2. Añadir en `docker-compose.yml` bajo `frontend` un `healthcheck` usando `wget --spider -q http://127.0.0.1:8080/ || exit 1` (verificando disponibilidad de `wget` en `nginxinc/nginx-unprivileged:alpine`).
  3. Validar con `docker compose config` y `docker compose up -d --build frontend` verificando estado `healthy`.

---

### [P2] Caché efímero de modelos ML, tags `:latest` sin fijar y topología de red/volúmenes inconsistente en Compose
- **Impacto:** Escalabilidad | Rendimiento | Seguridad
- **Target File(s):** `docker-compose.yml` (L29-L35, L106-L191, L195-L219, L335-L373)
- **Current State (Problema):**
  1. `ChromaDBDocumentStore` descarga `all-MiniLM-L6-v2` (~80 MB) y `faster-whisper` descarga el modelo `base` (~140 MB) en `/home/atenea/.cache` (HuggingFace / CTranslate2). Al no montar un volumen persistente para `/home/atenea/.cache` en `backend` (solo se monta `atenea_data:/app/data`), cada recreación de contenedor vuelve a descargar ~220 MB de modelos y falla en redes restringidas.
  2. `chroma-server` usa `chromadb/chroma:latest` (L107) y `minio` usa `cgr.dev/chainguard/minio:latest` (L336), y `langfuse-web`/`worker` usan el tag mutable `:3`, comprometiendo la reproducibilidad de despliegues.
  3. `redis` (L173) arranca con `--save "" --appendonly no` (sin persistencia), pero declara el volumen `atenea_redis_data:/data` (L181).
  4. `langfuse-web` (L215-L218) se conecta a `app-net` innecesariamente (ya comparte `data-net` con `backend`), exponiendo la interfaz de Langfuse al contenedor `frontend`.
  5. En `--profile scale`, `backend` carece de dependencia de ordenación frente a `postgres` y `chroma-server` (al pertenecer a distintos perfiles), pudiendo fallar en `lifespan` si arranca antes de que PostgreSQL acepte conexiones.
- **Desired Outcome (Objetivo):** Versiones fijadas en Compose, volumen persistente para caché de embeddings/STT, limpieza de redes/volúmenes muertos y espera resiliente o compose override para `--profile scale`.
- **Actionable Steps for Agent:**
  1. Añadir volumen `atenea_ml_cache:/home/atenea/.cache` al servicio `backend` en `docker-compose.yml` y declararlo en `volumes:`.
  2. Fijar tags concretos (preferiblemente con versión semántica y/o digest) para `chromadb/chroma`, `cgr.dev/chainguard/minio` y `langfuse`.
  3. Eliminar el volumen `atenea_redis_data` si Redis es puramente caché efímera, o habilitar AOF si debe sobrevivir reinicios.
  4. Retirar `app-net` de `langfuse-web` (mantener `npm-network` y `data-net`).
  5. Documentar o añadir archivo `docker-compose.scale.yml` (o retry de conexión en startup del backend) para garantizar espera a `postgres`/`chroma-server` cuando `scale` esté activo.

---

### [P2] Desfase de versiones Python, duplicación `requirements.txt`/`uv.lock` y brechas de calidad/seguridad en CI/CD
- **Impacto:** Arquitectura | Seguridad
- **Target File(s):** `.github/workflows/ci.yml` (L13-L109), `.github/workflows/docker-publish.yml` (L1-L89), `frontend/package.json` (L17-L19), `backend/pyproject.toml` (L5), `backend/requirements.txt` (L1-L56)
- **Current State (Problema):**
  1. **Tres versiones de Python distintas:** `approved_stack.md` exige Python `3.12+`, `backend/Dockerfile` construye con `python:3.11-slim`, `pyproject.toml` declara `>=3.11.5`, y `.github/workflows/ci.yml` (L26) ejecuta tests sobre Python `"3.14"`.
  2. **Divergencia de gestor de paquetes:** `ci.yml` (L31-L34) usa `pip install -r requirements.txt` + `pip install -e ".[dev]"` + `pip uninstall -y torchaudio || true`, mientras `backend/Dockerfile` usa `uv sync --frozen` con `uv.lock`. Mantener `requirements.txt` manualmente paralelo a `pyproject.toml` y `uv.lock` genera deriva de dependencias (ej. `opentelemetry-*` listados en `requirements.txt` no coinciden exactamente con `pyproject.toml`).
  3. **Checks faltantes y lint mutante en CI:** `ci.yml` no ejecuta linter Python (`ruff`), formateo, type-checking (`mypy` / `pyright`), ni `npm run build` de producción. Además `ci.yml` llama `npm run lint`, que en `frontend/package.json` (L18-L19) ejecuta `oxlint . --fix` y `eslint . --fix --cache` (mutando archivos en CI en vez de fallar con errores de lint).
  4. **Publicación desacoplada de CI y cuello de botella QEMU:** `docker-publish.yml` se dispara en cada push a `main` en paralelo con `ci.yml` sin requerir que los tests pasen ni ejecutar escaneo de CVEs (Trivy/Grype), y compila `linux/arm64` bajo emulación QEMU sobre paquetes C++/PyTorch.
- **Desired Outcome (Objetivo):** CI alineado con el runtime (`uv sync --frozen`, misma versión Python 3.12+ en todo el stack), linting no mutante, type-checking Python + build frontend + escaneo de contenedores, y publicación bloqueada hasta que CI pase.
- **Actionable Steps for Agent:**
  1. Alinear Python `3.12` (según `approved_stack.md`) en `backend/Dockerfile`, `backend/pyproject.toml` y `.github/workflows/ci.yml`, utilizando `astral-sh/setup-uv` y `uv sync --frozen --extra dev` en CI (generando `requirements.txt` desde `uv export` solo si sigue siendo necesario o retirándolo).
  2. Añadir pasos en `ci.yml` para `ruff check`, `mypy src`, y `npm run build` en frontend; dividir `package.json` en `lint` (solo comprobación, sin `--fix`) y `lint:fix`.
  3. Dividir `ci.yml` en jobs paralelos (`backend-qa`, `frontend-qa`, `e2e-playwright`, `sonar`) y subir `frontend/playwright-report` como artifact en `if: failure()`.
  4. Unificar o encadenar `docker-publish.yml` mediante `workflow_run` / `needs:` tras el paso exitoso de CI e incorporar análisis Trivy sobre las imágenes construidas.

---

### [P2] Gestión de Docker desde el proceso Python (`DockerObservabilityManager`) y scripts operativos frágiles
- **Impacto:** Arquitectura | Escalabilidad | Seguridad
- **Target File(s):** `backend/src/infrastructure/observability/docker_manager.py` (L17-L117), `backend/src/presentation/api/app.py` (L32-L44, L80-L92), `scripts/start.sh` (L28-L85), `scripts/download_models.sh` (L12-L42), `scripts/ingest_vault.py` (L127-L145)
- **Current State (Problema):**
  1. `app.py` registra `atexit(_cleanup_docker_on_exit)` y ejecuta `DockerObservabilityManager().ensure_stack_state(...)` / `stop_stack()` en `lifespan`. Dentro de Docker (`atenea-backend`), no existen ni el binario `docker`, ni `docker-compose.yml`, ni el socket; y en despliegues multi-worker (`uvicorn --workers > 1`) o multi-réplica en host, el cierre de un worker detendría Langfuse para los demás.
  2. `scripts/start.sh` lee `.env` con `grep`/`cut` (frágil ante espacios/comentarios), exige `pip install -r requirements.txt` en lugar de `uv`, espera arbitrariamente `sleep 2` antes de lanzar Vite y ejecuta `docker compose stop` global al salir.
  3. `scripts/download_models.sh` descarga modelos binarios externos (~380 MB entre Kokoro ONNX y Vosk) con `curl -L` sin verificar suma de comprobación SHA-256.
  4. `scripts/ingest_vault.py` lee `CHROMA_PATH` en vez de `CHROMA_PERSIST_DIR` e ignora `CHROMA_HOST`/`CHROMA_PORT`, impidiendo ingestar contra el servicio `chroma-server` del perfil `scale`.
- **Desired Outcome (Objetivo):** Separación estricta entre el ciclo de vida de la app y la orquestación de infraestructura externa, descarga verificada de artefactos y CLI alineado con `Settings`.
- **Actionable Steps for Agent:**
  1. Eliminar la gestión automática de `docker compose` desde `app.py` (`lifespan` y `atexit`), dejando la orquestación de Langfuse exclusivamente a `docker compose --profile observability` o a `scripts/start.sh` bajo flag explícito.
  2. Actualizar `scripts/download_models.sh` añadiendo checksums SHA-256 esperados (`sha256sum -c` / `shasum -a 256 -c`) tras cada descarga.
  3. Actualizar `scripts/ingest_vault.py` para aceptar `--chroma-host`/`--chroma-port` y leer `CHROMA_PERSIST_DIR` / `CHROMA_HOST` / `CHROMA_PORT` de forma coherente con `Settings`.
  4. Actualizar `scripts/start.sh` para usar `uv`, health-poll sobre `http://127.0.0.1:8000/health` en lugar de `sleep 2`, y parada selectiva solo de contenedores arrancados por el script.

