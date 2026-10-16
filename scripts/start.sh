#!/usr/bin/env bash
# =============================================================================
# ATENEA — Unified Development Startup Script
# Starts Backend (FastAPI), Frontend (Vite), and handles Langfuse/Docker lifecycle.
# =============================================================================

set -e

# Change to project root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================================="
echo "  🤖  Iniciando A.T.E.N.E.A. (AI Agent Assistant)"
echo "=========================================================="

# 1. Comprobar archivo de entorno
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    echo "⚠️  No se encontró .env. Creando .env a partir de .env.example..."
    cp .env.example .env
  else
    echo "❌ Error: No se encontró el archivo .env"
    exit 1
  fi
fi

# Leer estado de LANGFUSE_METRICS_ENABLED
LANGFUSE_ENABLED=$(grep -E "^LANGFUSE_METRICS_ENABLED=" .env | cut -d '=' -f2 | tr -d ' "' | tr '[:upper:]' '[:lower:]' || echo "false")

if [ "$LANGFUSE_ENABLED" = "true" ]; then
  echo "📊 Observabilidad: LANGFUSE ACTIVADO (Docker stack se gestionará automáticamente)"
else
  echo "⚡ Observabilidad: LANGFUSE DESACTIVADO (Modo local ligero sin Docker)"
fi

# 2. Comprobar entorno virtual de Python
if [ ! -d "backend/.venv" ]; then
  echo "❌ Error: No se encontró el entorno virtual en backend/.venv"
  echo "   Por favor ejecuta: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# 3. Comprobar node_modules en Frontend
if [ ! -d "frontend/node_modules" ]; then
  echo "📦 Instalando dependencias de frontend..."
  (cd frontend && npm install)
fi

# 4. Manejador de parada limpia al pulsar Ctrl+C
cleanup() {
  echo ""
  echo "🛑 Deteniendo servicios de Atenea..."
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true

  if [ "$LANGFUSE_ENABLED" = "true" ]; then
    echo "🐳 Deteniendo stack de Docker (Langfuse)..."
    docker compose stop 2>/dev/null || true
  fi

  echo "✅ Servidores frontend, backend y contenedores Docker detenidos."
  exit 0
}


trap cleanup SIGINT SIGTERM EXIT

# 5. Lanzar Backend en segundo plano
echo "🚀 Iniciando Backend (FastAPI / Uvicorn en http://localhost:8000)..."
(
  cd backend
  source .venv/bin/activate
  exec uvicorn src.presentation.api.app:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

# Breve espera para que FastAPI inicialice lifespan y Docker si corresponde
sleep 2

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
if [ "$LANGFUSE_ENABLED" = "true" ]; then
  echo "   - Langfuse Dashboard: http://localhost:3000"
fi
echo ""
echo "Presiona Ctrl+C para detener todos los servicios."
echo ""

# Esperar a que terminen los procesos
wait "$BACKEND_PID" "$FRONTEND_PID"
