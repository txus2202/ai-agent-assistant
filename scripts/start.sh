#!/usr/bin/env bash
# =============================================================================
# ATENEA — Unified Development Startup Script
# Starts Backend (FastAPI), Frontend (Vite), and optionally Langfuse via flag.
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WITH_LANGFUSE=false
for arg in "$@"; do
  case "$arg" in
    --with-langfuse)
      WITH_LANGFUSE=true
      ;;
    --help|-h)
      echo "Uso: ./scripts/start.sh [--with-langfuse]"
      echo "  --with-langfuse   Arranca la pila Docker de Langfuse (--profile observability)"
      echo "                    y detiene únicamente esos contenedores al cerrar."
      exit 0
      ;;
    *)
      echo "❌ Opción desconocida: $arg (usa --help para ver las opciones)" >&2
      exit 1
      ;;
  esac
done

read_env_value() {
  local target_key="$1"
  local env_file="$2"
  local line raw_val
  [[ -f "$env_file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%$'\r'}"
    line="${line#export }"
    case "$line" in
      ''|'#'*) continue ;;
      *) ;;
    esac
    if [[ "$line" =~ ^[[:space:]]*${target_key}[[:space:]]*=(.*)$ ]]; then
      raw_val="${BASH_REMATCH[1]}"
      raw_val="${raw_val#"${raw_val%%[![:space:]]*}"}"
      if [[ "$raw_val" =~ ^\"([^\"]*)\" ]] || [[ "$raw_val" =~ ^\'([^\']*)\' ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
      fi
      raw_val="${raw_val%%#*}"
      raw_val="${raw_val%"${raw_val##*[![:space:]]}"}"
      printf '%s' "$raw_val"
      return 0
    fi
  done < "$env_file"
}

echo "=========================================================="
echo "  🤖  Iniciando A.T.E.N.E.A. (AI Agent Assistant)"
echo "=========================================================="

# 1. Comprobar archivo de entorno
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    echo "⚠️  No se encontró .env. Creando .env a partir de .env.example..."
    cp .env.example .env
  else
    echo "❌ Error: No se encontró el archivo .env" >&2
    exit 1
  fi
fi

LANGFUSE_ENABLED="$(printf '%s' "$(read_env_value LANGFUSE_METRICS_ENABLED .env)" | tr '[:upper:]' '[:lower:]')"
if [[ -z "$LANGFUSE_ENABLED" ]]; then
  LANGFUSE_ENABLED="false"
fi

STARTED_LANGFUSE=false
if [[ "$WITH_LANGFUSE" == true ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Error: --with-langfuse requiere Docker instalado en PATH." >&2
    exit 1
  fi
  if [[ -z "$(docker compose --profile observability ps --status running -q langfuse-web 2>/dev/null || true)" ]]; then
    echo "📊 Arrancando pila Docker de Langfuse (--profile observability)..."
    docker compose --profile observability up -d langfuse-web langfuse-worker
    STARTED_LANGFUSE=true
  else
    echo "📊 Pila Docker de Langfuse ya activa; no se reiniciará ni detendrá al salir."
  fi
elif [[ "$LANGFUSE_ENABLED" == "true" ]]; then
  echo "📊 LANGFUSE_METRICS_ENABLED=true en .env (ejecuta con --with-langfuse o 'docker compose --profile observability up -d' si necesitas arrancar Langfuse)."
else
  echo "⚡ Observabilidad: LANGFUSE DESACTIVADO (Modo local ligero sin Docker)"
fi

# 2. Comprobar gestor/entorno de Python
USE_UV=false
if command -v uv >/dev/null 2>&1; then
  USE_UV=true
  if [[ ! -d "backend/.venv" ]]; then
    echo "📦 Creando entorno virtual backend/.venv con uv sync --frozen --extra dev..."
    (cd backend && uv sync --frozen --extra dev --no-install-project)
  fi
elif [[ ! -d "backend/.venv" ]]; then
  echo "❌ Error: No se encontró backend/.venv ni 'uv' en PATH." >&2
  echo "   Instala uv y ejecuta: cd backend && uv sync --frozen --extra dev" >&2
  exit 1
fi

# 3. Comprobar node_modules en Frontend
if [[ ! -d "frontend/node_modules" ]]; then
  echo "📦 Instalando dependencias de frontend..."
  (cd frontend && npm ci --ignore-scripts)
fi

BACKEND_PID=""
FRONTEND_PID=""

# 4. Manejador de parada limpia al pulsar Ctrl+C
cleanup() {
  echo ""
  echo "🛑 Deteniendo servicios de Atenea..."
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true

  if [[ "$STARTED_LANGFUSE" == true ]]; then
    echo "🐳 Deteniendo contenedores Langfuse iniciados por start.sh..."
    docker compose --profile observability stop langfuse-web langfuse-worker clickhouse minio postgres redis 2>/dev/null || true
  fi

  echo "✅ Servidores detenidos correctamente."
}

trap cleanup SIGINT SIGTERM EXIT

# 5. Lanzar Backend en segundo plano
echo "🚀 Iniciando Backend (FastAPI / Uvicorn en http://localhost:8000)..."
(
  cd backend
  if [[ "$USE_UV" == true ]]; then
    exec uv run --no-sync uvicorn src.presentation.api.app:app --reload --host 0.0.0.0 --port 8000
  else
    exec .venv/bin/uvicorn src.presentation.api.app:app --reload --host 0.0.0.0 --port 8000
  fi
) &
BACKEND_PID=$!

# Esperar a que /health responda (máx. ~30s)
HEALTH_READY=false
for _ in $(seq 1 60); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ El backend se detuvo durante el arranque." >&2
    exit 1
  fi
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    HEALTH_READY=true
    break
  fi
  sleep 0.5
done

if [[ "$HEALTH_READY" != true ]]; then
  echo "❌ Timeout esperando http://127.0.0.1:8000/health" >&2
  exit 1
fi

# 6. Lanzar Frontend
echo "💻 Iniciando Frontend (Vite en http://localhost:5173)..."
(
  cd frontend
  exec npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "✨ Atenea está lista:"
echo "   - Frontend UI:        http://localhost:5173"
echo "   - Backend API Docs:   http://localhost:8000/docs"
if [[ "$LANGFUSE_ENABLED" == "true" ]] || [[ "$WITH_LANGFUSE" == true ]]; then
  echo "   - Langfuse Dashboard: http://localhost:3000"
fi
echo ""
echo "Presiona Ctrl+C para detener todos los servicios."
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
