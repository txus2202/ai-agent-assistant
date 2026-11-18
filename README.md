# 🤖 AI-Agent-Assistant & ATENEA

<div align="center">

[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue.js-3.5+-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Playwright](<https://img.shields.io/badge/Playwright-E2E%20Tests%20(38%2F38)-2EAD33?style=for-the-badge&logo=playwright&logoColor=white>)](https://playwright.dev/)
[![Vitest](<https://img.shields.io/badge/Vitest-Unit%20Tests%20(380%2F380)-FCC72B?style=for-the-badge&logo=vitest&logoColor=black>)](https://vitest.dev/)
[![Pytest](<https://img.shields.io/badge/Pytest-Backend%20Tests%20(315%2F315)-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white>)](https://pytest.org/)
[![Docker](https://img.shields.io/badge/Docker-Isolated%20Deployment-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Clean Architecture](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-blueviolet?style=for-the-badge)](https://blog.cleancoder.com/)

**Motor Meta-Agéntico Declarativo y Asistente Técnico Consultivo de Arquitectura de Software**  
_Proyecto de Trabajo Fin de Máster (TFM) — Máster en Desarrollo con Inteligencia Artificial_  
**Autor:** Jesús Jiménez Vaquero ([@txus2202](https://github.com/txus2202))

</div>

---

## 📖 1. Visión General: La Dualidad del Sistema

Este proyecto aborda uno de los desafíos más críticos en el desarrollo de software impulsado por Inteligencia Artificial: **la separación estricta entre el motor de orquestación multi-agente y el dominio de aplicación del asistente**.

Para resolver este problema, la solución se estructura en dos niveles conceptuales y arquitecturales claramente delimitados:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  AI-AGENT-ASSISTANT                                    │
│                    (El Framework / Motor Generador Meta-Agéntico)                      │
│                                                                                        │
│  • Clean Architecture Modular (Dominio, Aplicación, Infraestructura, Presentación)     │
│  • Motor de Deliberación Colegiada y Orquestación Asíncrona (Supervisor Pattern)       │
│  • Protocolo Streaming WebSocket bidireccional y Checkpoints Human-in-the-Loop (HITL)  │
│  • Local-First Privacy (ChromaDB Vectorial, Faster-Whisper STT, Kokoro TTS, Vosk WW)   │
│  • Capa Agnóstica Multi-Proveedor LLM (Gemini, OpenAI, Anthropic, Ollama)              │
│  • Arnés Hermético de Pruebas E2E y Unitarias (Playwright + Vitest + Pytest)           │
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
│    - Atenea (Supervisor / Moderador Estratégico)                                       │
│    - Hermes (Intérprete de Lenguaje Natural)                                           │
│    - Ícaro (Arquitecto Innovador y Tecnologías Disruptivas)                            │
│    - Hestia (Arquitecta Senior, Clean Architecture y Estabilidad)                      │
│    - Sphinx (El Juez, Auditor de Riesgos y Evaluación de Trade-offs)                   │
│    - Hefesto (Especialista en DevSecOps, Infraestructura Cloud y Seguridad)            │
│    - Aracne (Diagramadora de Arquitectura en Mermaid en Tiempo Real)                   │
│    - Metis (Aprendizaje Continuo e Ingesta RAG de Fuentes Externas)                    │
│    - Fídias (Generación de Mockups y Artefactos Visuales)                              │
│    - Dédalo (Desarrollador Full-Stack y Maestro Artesano del Software)                 │
│    - Calíope (Documentación Técnica, ADRs y Diapositivas PPTX)                         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **`ai-agent-assistant` (El Framework)**:  
   Es el **motor meta-agéntico agnóstico al dominio**. Proporciona el ciclo de vida de los agentes, la gestión asíncrona de tareas, la ingesta vectorial RAG, el bus de eventos en streaming por WebSocket, los controles interactivos de supervisión humana (HITL), la pila de modelos de voz locales y el arnés de pruebas automatizado. El motor está completamente desacoplado del dominio mediante el test estático `test_decoupling_guard.py` (garantizando cero nombres de agentes acoplados en el código).

2. **`ATENEA` (La Aplicación Especializada)**:  
   Es la **instanciación y caso de estudio tecnológico de referencia**. Mediante los archivos declarativos [`agents.yaml`](agents.yaml) y [`topology.yaml`](topology.yaml), configura un equipo virtual completo de ingeniería y arquitectura de software que colabora en deliberación colegiada para diseñar, auditar y documentar sistemas de información de alta complejidad.

> [NOTA]
> Para profundizar en el marco teórico de la separación entre el Framework y la Aplicación, consulta el documento de arquitectura:  
> 📄 [docs/architecture/ai_agent_assistant_vs_atenea_concept.md](docs/architecture/ai_agent_assistant_vs_atenea_concept.md)

---

## 🏛️ 2. ATENEA: El Consejo Virtual de Arquitectura de Software

En su instanciación como **A.T.E.N.E.A.** (_Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas_), el sistema materializa un consejo colegiado de 11 agentes especialistas configurados declarativamente:

| Agente      | Rol en el Grafo Dialéctico          | Especialidad y Misión Técnica                                                                                | Artefacto / Herramienta Asociada                                                                                                                                                                  | RAG |
| :---------- | :---------------------------------- | :----------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-: |
| **Atenea**  | **Supervisora y Moderadora**        | Coordinación estratégica del debate, resolución de disensos y redacción del dictamen consolidado.            | Dictamen Arquitectónico Consolidado                                                                                                                                                               | No  |
| **Hermes**  | **Intérprete de Requerimientos**    | Traduce peticiones humanas en lenguaje natural a especificaciones técnicas formales y estructuradas.         | Especificación de Requerimientos                                                                                                                                                                  | No  |
| **Ícaro**   | **Arquitecto Proponente Innovador** | Plantea soluciones vanguardistas, arquitecturas event-driven, reactivas, microservicios y serverless.        | Propuesta Arquitectónica Disruptiva                                                                                                                                                               | Sí  |
| **Hestia**  | **Arquitecta Proponente Senior**    | Defensora de la prudencia, Clean Architecture, DDD, modularidad, mantenibilidad y resiliencia.               | Propuesta Arquitectónica Robusta                                                                                                                                                                  | Sí  |
| **Sphinx**  | **El Juez y Auditor Crítico**       | Análisis crítico de riesgos, estimación de costes, detección de cuellos de botella y balanceo de trade-offs. | Matriz de Riesgos y Evaluación Comparativa                                                                                                                                                        | Sí  |
| **Hefesto** | **Especialista DevSecOps**          | Hardening de seguridad, auditoría de permisos, pipelines CI/CD y contenedorización Cloud-Native.             | Manifiestos Docker, K8s y Directivas DevSecOps                                                                                                                                                    | Sí  |
| **Aracne**  | **Diagramadora de Arquitectura**    | Generación de diagramas técnicos interactivos en Mermaid (C4, secuencia, clases y topologías).               | Diagramas Interactivos SVG ([`DiagramModal.vue`](frontend/src/components/tools/DiagramModal.vue))                                                                                                 | Sí  |
| **Metis**   | **Especialista en Ingesta y RAG**   | Extracción, procesamiento y vectorización de PDFs, documentación técnica y URLs hacia ChromaDB.              | Indexación Vectorial RAG en Obsidian Vault                                                                                                                                                        | Sí  |
| **Fídias**  | **Diseñador Visual de Activos**     | Generación de diagramas de alto nivel, esquemas visuales y mockups de interfaces (HTML5/Imagen).             | Mockups Visuales y Layouts ([`ImageModal.vue`](frontend/src/components/tools/ImageModal.vue))                                                                                                     | No  |
| **Dédalo**  | **Desarrollador Full-Stack**        | Implementación de código funcional, pruebas de concepto (POCs), scripts y arquitecturas web con Clean Code.  | Código Fuente y Scripts ([`CodeModal.vue`](frontend/src/components/tools/CodeModal.vue))                                                                                                          | No  |
| **Calíope** | **Documentadora y Presentaciones**  | Elaboración de actas de decisión (ADRs), minutas en Markdown y diapositivas ejecutivas con exportación PPTX. | Documentos Markdown ([`DocumentModal.vue`](frontend/src/components/tools/DocumentModal.vue)) y Diapositivas PPTX ([`PresentationModal.vue`](frontend/src/components/tools/PresentationModal.vue)) | Sí  |

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
| **✓ Aceptar** | `decision: "approve"` | _"aceptar"_, _"aprobar"_, _"adelante"_, _"conforme"_, _"de acuerdo"_ | Valida la fase actual y continúa hacia la siguiente etapa de la topología. |
| **✏ Refinar** | `decision: "refine"` | _"refinar"_, _"corregir"_, _"cambiar"_, _"modificar"_, _"ajustar"_ | Reabre la fase actual incorporando feedback en lenguaje natural; activa el micrófono automáticamente. |
| **🔀 Desviar** | `decision: "divert"` | _"desviar"_, _"bifurcar"_, _"derivar"_, _"delegar"_ | Omite las fases intermedias y delega el turno directamente a uno o varios especialistas seleccionados. |
| **📦 Consolidar** | `decision: "consolidate"` | _"consolidar"_, _"consolida"_, _"resumir"_, _"resumen"_ | Concluye el debate de forma anticipada y ordena a Atenea redactar y consolidar el dictamen final con la información acumulada hasta ese punto. |
| **🛑 Finalizar** | `decision: "finish"` | _"finalizar"_, _"terminar"_, _"detener"_, _"parar"_, _"concluir"_, _"fin"_ | Detiene y da por finalizado el debate de inmediato en seco, **sin realizar consolidación** ni generar dictamen final. |
| **🔄 Reintentar** | `decision: "retry"` | _"reintentar"_, _"reintenta"_, _"repetir"_, _"repite"_ | Reejecuta la fase actual para los agentes seleccionados sin avanzar en la topología. |
| **✗ Rechazar** | `decision: "reject"` | _"rechazar"_, _"denegar"_, _"cancela"_, _"cancelar"_, _"descartar"_ | Descarta la propuesta actual y fuerza una re-ejecución con alternativas diferentes. |

- **Interrupción Inmediata de Voz (Barge-In)**: Cualquier interacción (clic o comando) detiene instantáneamente la síntesis de voz en reproducción (`stopTts()`).
- **Comando Universal de Silencio**: Disponible en todo momento diciendo _"silencio"_, _"silenciar"_, _"calla"_ o _"cállate"_.
- **Selección Contextual de Agentes**: Al pronunciar el nombre de un especialista durante un checkpoint HITL (p. ej. _"Hestia"_), el sistema lo conmuta en la lista de destinatarios para la acción de desvío.

---

## 🧩 5. Extensibilidad Declarativa y Modularidad de Herramientas

La arquitectura del motor **`ai-agent-assistant`** está diseñada bajo el principio _Open/Closed_ (abierto a la extensión, cerrado a la modificación): permite generar un asistente para cualquier otro sector (auditoría legal, medicina, finanzas, educación) **sin tocar una sola línea de código** y extender la interfaz gráfica mediante herramientas especializadas.

### 5.1 Definición Declarativa de Asistentes y Topologías

Para crear un nuevo asistente o modificar el comportamiento de Atenea, solo es necesario parametrizar dos archivos en la raíz:

1. **[`agents.yaml`](agents.yaml)**: Catálogo de especialistas, sus system prompts, herramientas asignadas, flags RAG y alias fonéticos para el motor de voz.
2. **[`topology.yaml`](topology.yaml)**: Grafo de deliberación que asigna qué agentes asumen los roles de `supervisor`, `interpreters`, `proposers`, `reviewers`, `evaluators` e `implementers`, así como las rondas de revisión previas a cada checkpoint humano.

El test automatizado estático [`test_decoupling_guard.py`](backend/tests/application/agents/test_decoupling_guard.py) audita continuamente el repositorio para asegurar que ningún nombre de agente de Atenea se filtre o quede acoplado en las capas internas del framework.

### 5.2 Arquitectura Modular de Herramientas en el Frontend (`frontend/src/components/tools/`)

A diferencia de los asistentes conversacionales estándar que devuelven bloques de texto monolíticos, ATENEA desacopla los tipos de artefactos técnicos generados mediante un **subsistema modular de modales interactivos** en [`frontend/src/components/tools/`](frontend/src/components/tools/):

- **[`CodeModal.vue`](frontend/src/components/tools/CodeModal.vue) (Dédalo - Código y POCs)**: Visor de código fuente con resaltado de sintaxis multilenguaje, numeración de líneas, botón de copiado rápido con confirmación háptica y descarga directa del archivo con la extensión correspondiente.
- **[`DiagramModal.vue`](frontend/src/components/tools/DiagramModal.vue) (Aracne - Diagramas Mermaid)**: Renderizador interactivo en tiempo real de diagramas SVG con controles de zoom dinámico (rueda de ratón o botones), desplazamiento táctil o por arrastre (pan), visualización a pantalla completa y exportación vectorial a `.svg`.
- **[`DocumentModal.vue`](frontend/src/components/tools/DocumentModal.vue) (Calíope - Minutas y ADRs)**: Visor tipográfico de especificaciones técnicas, actas de deliberación y Registros de Decisiones de Arquitectura (ADRs) con soporte para formato GitHub Flavored Markdown (GFM).
- **[`PresentationModal.vue`](frontend/src/components/tools/PresentationModal.vue) (Calíope - Diapositivas y PPTX)**: Reproductor de presentaciones en modo proyector con navegación por teclado/swipe táctil, vista en cuadrícula de miniaturas y exportador binario cliente a presentaciones de Microsoft PowerPoint (`.pptx`) utilizando la librería `PptxGenJS`.
- **[`ImageModal.vue`](frontend/src/components/tools/ImageModal.vue) (Fídias - Mockups y Gráficos)**: Visor de alta resolución para esquemas visuales, wireframes generativos y prototipos de interfaces.

> **Extensibilidad de la UI**: Añadir un nuevo tipo de entregable (p. ej., tablas financieras interactivas o visores de métricas) no requiere modificar el núcleo del chat ni el bus WebSocket: basta con crear un nuevo componente modal en `frontend/src/components/tools/` y registrar su trigger.

---

## 🛡️ 6. Seguridad y Enfoque Local-First

- 🔒 **Soberanía y Privacidad Total**: El conocimiento empresarial almacenado en el Obsidian Vault se indexa exclusivamente en local mediante **ChromaDB**. Ningún fragmento de documentación interna se comparte entre usuarios no autorizados.
- 🗣️ **Modelos de Audio Locales**:
  - **Faster-Whisper**: Transcripción de voz (STT) ejecutada en local.
  - **Kokoro ONNX**: Síntesis de voz neural (TTS) de baja latencia sin consumo de APIs externas.
  - **Vosk**: Reconocimiento continuo de palabras de activación (_wake words_) en segundo plano.
- 🛡️ **Aislamiento Multi-Tenant y RBAC**: Sistema de autenticación con tokens de sesión seguros, roles diferenciados (`admin` y `user`), contraseñas hasheadas con `Argon2id` / `bcrypt` y repositorios SQLite aislados por `user_id`.
- 🌐 **Protección Anti-Indexación**: Triple barrera (`noindex, nofollow` en HTML, denegación universal en `robots.txt` y cabecera HTTP `X-Robots-Tag` en Nginx) para evitar cualquier rastreo en internet al publicarlo en VPS o entornos remotos.

---

## 🧪 7. Arnés de Pruebas y Aseguramiento de la Calidad

El sistema cuenta con un arnés de pruebas automatizado (_Test Harness_) integral de **733 pruebas automatizadas pasando con éxito (100% pass rate)** que garantiza la estabilidad del software con **coste cero en consumo de tokens**:

1. **Suite End-to-End con Playwright (38/38 tests pasando)**:
   - Ejecutados en navegadores reales: Chromium (Escritorio 1280x720) y Mobile Chrome (Pixel 7).
   - Valida el flujo dialéctico completo: autenticación y setup inicial, guardias de navegación, streaming por WebSockets, selector multi-dominio, checkpoints HITL con todas sus variantes de control, modales de presentaciones PPTX, diagramas interactivos Mermaid con zoom/pan, visor de código e historial reactivo de debates.
2. **Suite Unitaria y de Componentes Frontend (380/380 tests en Vitest)**:
   - Cobertura exhaustiva de componentes Vue 3, composables reactivos, utilidades de parsing y stores centralizados Pinia con mocks de WebSocket y APIs.
3. **Suite de Backend e Integración (315/315 tests en Pytest)**:
   - Pruebas asíncronas con `ASGITransport` cubriendo casos de uso, repositorios SQLite, embeddings de ChromaDB, validación de schemas Pydantic, seguridad JWT/Argon2id y adaptadores LLM.
4. **Calidad de Código, Tipado Estricto y Desacoplamiento Arquitectónico**:
   - `vue-tsc --build`: 0 errores de tipado estricto TypeScript.
   - `oxlint` + `eslint`: 0 errores y 0 advertencias de linter.
   - [`test_decoupling_guard.py`](backend/tests/application/agents/test_decoupling_guard.py): Auditoría estática que verifica que el código del motor no contenga referencias codificadas a los nombres de agentes de la aplicación.

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

_(Descarga los pesos de Kokoro ONNX TTS y el modelo pequeño de Vosk en la carpeta `backend/models`)_.

### 2. Configuración de Entorno (`.env`)

```bash
cp .env.example .env
```

Configura tus claves de API para los proveedores de LLM que desees utilizar (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

### 3. Arranque del Sistema

#### Opción A: Despliegue con Docker Compose (Recomendado para Evaluación Rápida)

Levanta todos los servicios con aislamiento de red, base de datos y telemetría en un único comando:

```bash
docker compose up -d
```

#### Opción B: Script Local Unificado

Levanta el backend FastAPI, el frontend Vue 3 y gestiona los servicios auxiliares:

```bash
./scripts/start.sh
```

#### Opción C: Desarrollo en Dos Terminales

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

Desde la carpeta `backend/`:

```bash
# Ejecutar todas las pruebas unitarias y de integración
pytest tests/ -v
```

### 5. Servicios Disponibles

- **Interfaz de Usuario (ATENEA)**: [http://localhost:5173](http://localhost:5173)
- **API Backend y Swagger OpenAPI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Panel de Observabilidad Langfuse** (opcional): [http://localhost:3000](http://localhost:3000)

---

## 🏛️ 9. Licencia y Créditos Académicos

Este proyecto ha sido desarrollado como **Trabajo Fin de Máster (TFM)** en el **Máster en Desarrollo con Inteligencia Artificial**.

- **Autor:** Jesús Jiménez Vaquero ([@txus2202](https://github.com/txus2202))
- **Repositorio:** [https://github.com/txus2202/ai-agent-assistant](https://github.com/txus2202/ai-agent-assistant)
- **Licencia:** Propietaria / Todos los derechos reservados — _Uso exclusivo para Evaluación Académica (TFM)_. Consulta el archivo [LICENSE](LICENSE) para más detalles.
