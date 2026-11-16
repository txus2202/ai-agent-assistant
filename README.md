# 🤖 AI-Agent-Assistant & ATENEA

<div align="center">

[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue.js-3.5+-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Playwright](https://img.shields.io/badge/Playwright-E2E%20Tests%20(38%2F38)-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Vitest](https://img.shields.io/badge/Vitest-Unit%20Tests%20(377%2F377)-FCC72B?style=for-the-badge&logo=vitest&logoColor=black)](https://vitest.dev/)
[![Docker](https://img.shields.io/badge/Docker-Isolated%20Deployment-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Clean Architecture](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-blueviolet?style=for-the-badge)](https://blog.cleancoder.com/)

**Motor Meta-Agéntico Declarativo y Asistente Técnico Consultivo de Arquitectura de Software**  
*Proyecto de Trabajo Fin de Máster (TFM) — Máster en Desarrollo con Inteligencia Artificial*  
**Autor:** Jesús Jiménez Vaquero

</div>

---

## 📖 1. Visión General: La Dualidad del Sistema

Este proyecto aborda uno de los desafíos más críticos en el desarrollo de software impulsado por Inteligencia Artificial: **la separación estricta entre el motor de orquestación multi-agente y el dominio de aplicación del asistente**.

Para resolver este problema, la solución se estructura en dos niveles conceptuales y arquitecturales claramente delimitados:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  AI-AGENT-ASSISTANT                                    │
│                    (El Framework / Motor Generador Meta-Agéntico)                     │
│                                                                                        │
│  • Clean Architecture Modular (Dominio, Aplicación, Infraestructura, Presentación)     │
│  • Motor de Deliberación Colegiada y Orquestación Asíncrona (Supervisor Pattern)       │
│  • Protocolo Streaming WebSocket bidireccional y Checkpoints Human-in-the-Loop (HITL)  │
│  • Local-First Privacy (ChromaDB Vectorial, Faster-Whisper STT, Kokoro TTS, Vosk WW)   │
│  • Capa Agnóstica Multi-Proveedor LLM (Gemini, OpenAI, Anthropic, Ollama)              │
│  • Arnés Hermético de Pruebas E2E y Unitarias (Playwright + Vitest + Pytest)          │
│                                                                                        │
│                        CONFIGURACIÓN DECLARATIVA (Zero Code)                           │
│                     ┌────────────────────────┬─────────────────────────┐               │
│                     │      agents.yaml       │      topology.yaml      │               │
│                     │  (Catálogo de Agentes) │  (Grafo de Deliberación)│               │
│                     └───────────┬────────────┴────────────┬────────────┘               │
└─────────────────────────────────┼─────────────────────────┼────────────────────────────┘
                                  ▼                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                       ATENEA                                           │
│                       (La Aplicación / Caso de Uso Referencial)                        │
│                                                                                        │
│  • "Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas"              │
│  • Consejo Virtual de Arquitectura de Software y Equipo de IT Integral:                │
│    - Atenea (Supervisor / Moderador Estratégico)                                      │
│    - Hermes (Intérprete de Lenguaje Natural)                                          │
│    - Ícaro (Arquitecto Innovador y Tecnologías Disruptivas)                           │
│    - Hestia (Arquitecta Senior, Clean Architecture y Estabilidad)                     │
│    - Sphinx (El Juez, Auditor de Riesgos y Evaluación de Trade-offs)                   │
│    - Hefesto (Especialista en DevSecOps, Infraestructura Cloud y Seguridad)           │
│    - Aracne (Diagramadora de Arquitectura en Mermaid en Tiempo Real)                  │
│    - Metis (Aprendizaje Continuo e Ingesta RAG de Fuentes Externas)                   │
│    - Fídias (Generación de Mockups y Artefactos Visuales)                             │
│    - Dédalo (Generador de Diapositivas y Presentaciones Técnicas)                     │
│    - Calíope (Documentación Técnica y Minutas Estructuradas en Markdown)              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **`ai-agent-assistant` (El Framework)**:  
   Es el **motor meta-agéntico agnóstico al dominio**. Proporciona el ciclo de vida de los agentes, la gestión asíncrona de tareas, la ingesta vectorial RAG, el bus de eventos en streaming por WebSocket, los controles interactivos de supervisión humana (HITL), la pila de modelos de voz locales y el arnés de pruebas automatizado. El motor está completamente desacoplado del dominio mediante el test estático `test_decoupling_guard.py` (garantizando cero nombres de agentes acoplados en el código).

2. **`ATENEA` (La Aplicación Especializada)**:  
   Es la **instanciación y caso de estudio tecnológico de referencia**. Mediante los archivos declarativos [`agents.yaml`](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/agents.yaml) y [`topology.yaml`](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/topology.yaml), configura un equipo virtual completo de ingeniería y arquitectura de software que colabora en deliberación colegiada para diseñar, auditar y documentar sistemas de información de alta complejidad.

> [!NOTE]
> Para profundizar en el marco teórico de la separación entre el Framework y la Aplicación, consulta el documento de arquitectura:  
> 📄 [docs/architecture/ai_agent_assistant_vs_atenea_concept.md](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/docs/architecture/ai_agent_assistant_vs_atenea_concept.md)

---

## 🏛️ 2. ATENEA: El Consejo Virtual de Arquitectura de Software

En su instanciación como **A.T.E.N.E.A.** (*Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas*), el sistema materializa un consejo colegiado de 11 agentes especialistas:

| Agente | ID Sistema | Rol en el Consejo | Especialidad y Misión | RAG |
| :--- | :--- | :--- | :--- | :---: |
| **Atenea** | `supervisor` | **Supervisora y Moderadora** | Coordinación estratégica del debate, resolución de disensos y redacción del dictamen consolidado. | No |
| **Hermes** | `nl_interpreter` | **Intérprete de Requerimientos** | Traduce peticiones humanas en lenguaje natural a requerimientos técnicos formales y estructurados. | No |
| **Ícaro** | `innovator_architect` | **Arquitecto Innovador** | Plantea soluciones vanguardistas, arquitecturas event-driven, microservicios, serverless y tecnologías emergentes. | Sí |
| **Hestia** | `senior_architect` | **Arquitecta Senior** | Defensora de la prudencia, Clean Architecture, DDD, modularidad, mantenibilidad y resiliencia operativa. | Sí |
| **Sphinx** | `the_judge` | **El Juez y Auditor** | Análisis crítico de riesgos, cálculo de costes, detección de cuellos de botella y balanceo de trade-offs. | Sí |
| **Hefesto** | `devops_secops` | **Especialista DevSecOps** | Hardening de seguridad, auditoría de permisos, CI/CD, contenedorización Docker/Kubernetes y cloud native. | Sí |
| **Aracne** | `diagrammer` | **Diagramadora de Arquitectura** | Generación de diagramas técnicos interactivos en Mermaid (C4, secuencia, diagramas de clases y topologías). | Sí |
| **Metis** | `learning` | **Especialista en Ingesta y RAG** | Extracción, procesamiento y vectorización de PDFs, documentación técnica y URLs hacia el vector store. | Sí |
| **Fídias** | `fídias` | **Diseñador Visual de Activos** | Generación de diagramas de alto nivel, esquemas visuales y mockups de interfaces mediante IA generativa. | No |
| **Dédalo** | `dedalo` | **Arquitecto de Presentaciones** | Estructuración de presentaciones ejecutivas en diapositivas Markdown con exportación a PPTX y HTML interactivo. | No |
| **Calíope** | `caliope` | **Documentadora Técnica** | Elaboración de actas de decisión (ADRs), especificaciones de requerimientos y minutas en Markdown en el Vault. | Sí |

---

## 🔄 3. Topología de Deliberación Colegiada (`topology.yaml`)

El flujo de trabajo dialéctico está modelado como un grafo acíclico dirigido (DAG) con fases de ejecución en paralelo y puntos de supervisión humana obligatorios:

```mermaid
flowchart TD
    User([Consulta de Arquitectura]) --> Triage{Triage Estratégico<br/>Supervisor: Atenea}
    
    subgraph Phase1 [Fase 1: Interpretación y Formalización]
        Triage -->|Consulta compleja| Interpreters["Hermes (Intérprete)"]
        Interpreters --> HITL1{Checkpoint HITL #1:<br/>Requerimientos Formalizados}
    end

    subgraph Phase2 [Fase 2: Propuestas en Paralelo y Peer Review]
        HITL1 -->|Aprobado| Proposers["Ícaro (Innovador) + Hestia (Senior)<br/><i>Ejecución concurrente (asyncio.gather) con RAG</i>"]
        Proposers --> ReviewLoop{"Revisión y Crítica Cruzada<br/>(Sphinx: The Judge)"}
        ReviewLoop <-->|Rondas Iterativas| ReviewLoop
        ReviewLoop --> HITL2{Checkpoint HITL #2:<br/>Selección de Alternativa}
    end

    subgraph Phase3 [Fase 3: Auditoría y Veredicto]
        HITL2 -->|Opción elegida| Evaluators["Sphinx (Auditoría de Riesgos y Trade-offs)"]
        Evaluators --> HITL3{Checkpoint HITL #3:<br/>Veredicto Final}
    end

    subgraph Phase4 [Fase 4: Implementación y Artefactos]
        HITL3 -->|Aprobado| Implementers["Aracne (Diagramas Mermaid) + Hefesto (DevSecOps)<br/><i>Ejecución paralela</i>"]
        Implementers --> Caliope["Calíope (Documentación en Vault)"]
        Caliope --> Consolidation["Consolidación Autorizada (Atenea)"]
    end

    Consolidation --> FinalDoc([Dictamen Arquitectónico Consolidado])
```

---

## 🎯 4. Gobernanza Human-In-The-Loop (HITL) y Control por Voz

El operador humano mantiene la gobernanza total del proceso deliberativo en cada punto de control, tanto desde la interfaz gráfica reactiva como mediante comandos de voz contextuales en tiempo real:

| Acción HITL | Payload de Control | Disparadores de Voz (Vosk) | Impacto en la Deliberación |
| :--- | :--- | :--- | :--- |
| **✓ Aceptar** | `decision: "approve"` | *"aceptar"*, *"aprobar"*, *"adelante"*, *"conforme"*, *"de acuerdo"* | Valida la fase actual y continúa hacia la siguiente etapa de la topología. |
| **✏ Refinar** | `decision: "refine"` | *"refinar"*, *"corregir"*, *"cambiar"*, *"modificar"*, *"ajustar"* | Reabre la fase actual incorporando feedback en lenguaje natural; activa el micrófono automáticamente. |
| **🔀 Desviar** | `decision: "divert"` | *"desviar"*, *"bifurcar"*, *"derivar"*, *"delegar"* | Omite las fases intermedias y delega el turno directamente a uno o varios especialistas seleccionados. |
| **🏁 Finalizar** | `decision: "finish"` | *"finalizar"*, *"terminar"*, *"concluir"*, *"fin"* | Concluye el debate de inmediato y ordena a Atenea redactar la síntesis final con los datos recopilados. |
| **✗ Rechazar** | `decision: "reject"` | *"rechazar"*, *"denegar"*, *"cancela"*, *"cancelar"*, *"descartar"* | Descarta la propuesta actual y fuerza una re-ejecución con alternativas diferentes. |

- **Interrupción Inmediata de Voz (Barge-In)**: Cualquier interacción (clic o comando) detiene instantáneamente la síntesis de voz en reproducción (`stopTts()`).
- **Comando Universal de Silencio**: Disponible en todo momento diciendo *"silencio"*, *"silenciar"*, *"calla"* o *"cállate"*.
- **Selección Contextual de Agentes**: Al pronunciar el nombre de un especialista durante un checkpoint HITL (p. ej. *"Hestia"*), el sistema lo conmuta en la lista de destinatarios para la acción de desvío.

---

## 🧩 5. Extensibilidad Declarativa: Creación de Nuevos Asistentes

La gran ventaja del motor **`ai-agent-assistant`** es que permite generar un asistente para cualquier otro sector (auditoría legal, medicina, finanzas, educación) **sin tocar una sola línea de código**. 

Solo es necesario definir:

1. **[`agents.yaml`](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/agents.yaml)**: Catálogo de especialistas, sus system prompts, herramientas, flags RAG y alias fonéticos.
2. **[`topology.yaml`](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/topology.yaml)**: Grafo de deliberación asignando qué agentes asumen los slots de `supervisor`, `interpreters`, `proposers`, `reviewers`, `evaluators` e `implementers`.

El test automatizado `test_decoupling_guard.py` audita continuamente el repositorio para asegurar que ningún nombre de agente de Atenea se filtre o quede acoplado en las capas internas del framework.

---

## 🛡️ 6. Seguridad y Enfoque Local-First

- 🔒 **Soberanía y Privacidad Total**: El conocimiento empresarial almacenado en el Obsidian Vault se indexa exclusivamente en local mediante **ChromaDB**. Ningún fragmento de documentación interna se comparte entre usuarios no autorizados.
- 🗣️ **Modelos de Audio Locales**:
  - **Faster-Whisper**: Transcripción de voz (STT) ejecutada en local.
  - **Kokoro ONNX**: Síntesis de voz neural (TTS) de baja latencia sin consumo de APIs externas.
  - **Vosk**: Reconocimiento continuo de palabras de activación (*wake words*) en segundo plano.
- 🛡️ **Aislamiento Multi-Tenant y RBAC**: Sistema de autenticación con tokens de sesión seguros, roles diferenciados (`admin` y `user`), contraseñas hasheadas con `Argon2id` / `bcrypt` y repositorios SQLite aislados por `user_id`.
- 🌐 **Protección Anti-Indexación**: Triple barrera (`noindex, nofollow` en HTML, denegación universal en `robots.txt` y cabecera HTTP `X-Robots-Tag` en Nginx) para evitar cualquier rastreo en internet al publicarlo en VPS o entornos remotos.

---

## 🧪 7. Arnés de Pruebas y Aseguramiento de la Calidad

El sistema cuenta con un arnés de pruebas automatizado (*Test Harness*) integral que garantiza la estabilidad del software con **coste cero en consumo de tokens**:

1. **Suite End-to-End con Playwright (38/38 tests pasando)**:
   - Ejecutados en Chromium (Escritorio 1280x720) y Mobile Chrome (Pixel 7).
   - Valida el ciclo completo: setup inicial, login, guardias de ruta, streaming WebSocket, selector de agentes, checkpoints HITL, modales de presentaciones, diagramas Mermaid interactivos con zoom, visor de código e historial de conversaciones.
2. **Suite Unitaria y de Componentes (377/377 tests pasando)**:
   - Vitest en el frontend cubriendo componentes Vue 3, composables, utilidades y stores Pinia.
   - Pytest en el backend con `ASGITransport` y base de datos SQLite en memoria (`:memory:`).
3. **Calidad de Código y Tipado Estricto**:
   - `vue-tsc --build`: 0 errores de tipado TypeScript.
   - `oxlint` + `eslint`: 0 errores y 0 advertencias de linter.

---

## 🚀 8. Guía de Instalación y Despliegue

### Requisitos Previos
- Python 3.14+
- Node.js 24+ y npm
- Docker y Docker Compose (opcional para telemetría Langfuse)

### 1. Descarga de Modelos de Inteligencia Artificial Locales
Para garantizar la privacidad, los modelos de voz operan en tu propia máquina. Descárgalos ejecutando:
```bash
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```
*(Descarga los pesos de Kokoro ONNX TTS y el modelo pequeño de Vosk en la carpeta `backend/models`)*.

### 2. Configuración de Entorno (`.env`)
```bash
cp .env.example .env
```
Configura tus claves de API para los proveedores de LLM que desees utilizar (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

### 3. Arranque del Sistema

#### Opción A: Script Unificado (Recomendado)
Levanta el backend FastAPI, el frontend Vue 3 y gestiona los contenedores auxiliares:
```bash
./scripts/start.sh
```

#### Opción B: Desarrollo en Dos Terminales
- **Terminal 1 (Backend FastAPI):**
  ```bash
  cd backend
  source .venv/bin/activate
  uvicorn src.presentation.api.app:app --reload
  ```
- **Terminal 2 (Frontend Vue 3 / Vite):**
  ```bash
  cd frontend
  npm run dev
  ```

### 4. Ejecución del Arnés de Pruebas
Desde la carpeta `frontend/`:
```bash
# Lanzar todas las pruebas E2E con Playwright (Desktop + Mobile)
npm run test:e2e

# Abrir el inspector visual interactivo de Playwright
npm run test:e2e:ui

# Ejecutar las pruebas unitarias
npm run test:unit
```

### 5. Servicios Disponibles
- **Interfaz de Usuario (ATENEA)**: [http://localhost:5173](http://localhost:5173)
- **API Backend y Swagger OpenAPI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Panel de Observabilidad Langfuse** (opcional): [http://localhost:3000](http://localhost:3000)

---

## 🏛️ 9. Licencia y Créditos Académicos

Este proyecto ha sido desarrollado como **Trabajo Fin de Máster (TFM)** en el **Máster en Desarrollo con Inteligencia Artificial**.

- **Autor:** Jesús Jiménez Vaquero
- **Repositorio:** [https://github.com/txus2202/ai-agent-assistant](https://github.com/txus2202/ai-agent-assistant)
- **Licencia:** Propietaria / Todos los derechos reservados — *Uso exclusivo para Evaluación Académica (TFM)*. Consulta el archivo [LICENSE](LICENSE) para más detalles.
