# Documento de Diseño de Software (SDD): Aprendizaje Multi-Fuente y Memoria Persistente con Metis

## 1. Contexto y Objetivos
**Metis** (`learning`) es la bibliotecaria y guardiana de la memoria a largo plazo del sistema de agentes ATENEA. Actualmente el sistema cuenta con ChromaDB y extractores básicos para PDFs y URLs, pero requiere evolucionar hacia un subsistema de **aprendizaje continuo, multi-fuente y contextual**:

1. **Ingesta Multi-Fuente:** Capacidad de extraer y asimilar conocimiento desde:
   - Archivos PDF (`.pdf`).
   - Archivos Markdown (`.md`) y notas técnicas.
   - Páginas web / documentación vía URL (`http/https`).
   - Imágenes técnicas y diagramas de arquitectura (`.png`, `.jpg`, `.jpeg`, `.webp`) mediante visión multimodal LLM.
2. **Interacción Conversacional Inteligente (Sin falso guardado):**
   - Permitir dialogar con Metis fluidamente sin necesidad de adjuntar archivos.
   - Consultar la base de conocimiento (`uses_rag: true`) sin contaminar el almacén vectorial.
   - Detectar directivas explícitas de memorización (ej. *"Aprende esto: ..."*, *"Memoriza la siguiente regla: ..."*) para vectorizar solo conocimiento de valor real.
3. **Aprendizaje de Soluciones y Sesiones:**
   - Opción explícita al término de un debate arquitectónico para que Metis sintetice y guarde la solución consensuada.
   - Capacidad en cualquier diálogo multi-agente de pedirle a Metis: *"Aprende de lo que hemos hablado"* / *"Sintetiza lo acordado"*.

---

## 2. Arquitectura del Subsistema de Conocimiento

```mermaid
flowchart TD
    User([Usuario]) -->|Adjunta archivo / URL / Imagen| UploadAPI[/api/upload & Ingest/]
    User -->|Chat: 'Aprende esto: ...'| MetisChat[Metis Agent]
    User -->|Botón: 'Aprender Solución'| LearnSessionAPI[/api/learning/session]

    subgraph "Extractores Multi-Fuente"
        PDFExt[PDFExtractor - PyMuPDF]
        URLExt[URLExtractor - httpx + bs4]
        MDExt[MarkdownExtractor - Frontmatter + Sections]
        ImgExt[ImageExtractor - Multimodal Vision LLM]
    end

    UploadAPI --> PDFExt & URLExt & MDExt & ImgExt

    subgraph "Pipeline de Aprendizaje (LearnFromSource)"
        Synthesizer[Sintetizador LLM - Estructura Vault]
        VaultStorage[(Obsidian Vault: vault/learned/)]
        IngestVault[IngestVault Service]
        ChromaStore[(ChromaDB Vector Store)]
    end

    PDFExt & URLExt & MDExt & ImgExt --> Synthesizer
    MetisChat -->|Directiva explícita| Synthesizer
    LearnSessionAPI -->|Historial / Solución| Synthesizer

    Synthesizer -->|Guarda .md con frontmatter| VaultStorage
    VaultStorage --> IngestVault
    IngestVault -->|Embeddings + Chunks| ChromaStore

    ChromaStore -->|RAG Retrieval| QueryVault[QueryVault Service]
    QueryVault -->|Contexto relevante| MetisChat
```

---

## 3. Especificación Técnica Backend

### 3.1 Extractores de Fuentes (`backend/src/infrastructure/learning/`)
Se amplía la familia de extractores bajo un contrato unificado:
- **`MarkdownExtractor`:** Lee archivos `.md`, preserva el YAML frontmatter existente si lo hay o normaliza encabezados.
- **`ImageExtractor`:** Toma la ruta a una imagen local o base64, invoca al adaptador LLM con capacidades multimodales (ej. Gemini o Claude/OpenAI) con un prompt especializado en diagramas y esquemas técnicos (*"Extrae y explica exhaustivamente la arquitectura, flujos, componentes y texto contenidos en esta imagen técnica en formato Markdown estructurado"*).
- **`SourceType` enum:** `PDF = "pdf"`, `URL = "url"`, `MARKDOWN = "markdown"`, `IMAGE = "image"`, `TEXT = "text"`.

### 3.2 Servicio de Ingesta Unificado (`LearnFromSource`)
- Acepta los nuevos `SourceType`.
- Si `SourceType == IMAGE`: invoca a `ImageExtractor` con el LLM multimodal.
- Si `SourceType == TEXT` (directiva conversacional): estructura directamente el texto proporcionado.
- Genera el archivo en `vault_root/learned/{fecha}_{slug}.md`.
- Ejecuta `IngestVault.run()` para que esté disponible de inmediato en ChromaDB.

### 3.3 Guardrail Semántico en Metis (`agents.yaml` + `SubAgentRunner` / `Supervisor`)
- **Configuración de Metis:** Cambiar `uses_rag: true` en `agents.yaml` para que Metis pueda recuperar conocimiento previo al responder preguntas.
- **Detección de Aprendizaje Conversacional:**
  - En el chat directo con Metis, se analizan patrones de entrada como `r"(?i)^(?:aprende\s+esto|aprende|memoriza|guarda\s+este\s+conocimiento)[:\s]+(.+)"`.
  - Si coincide: Se extrae el contenido, se procesa mediante `LearnFromSource(source_type=TEXT)`, y Metis responde con su confirmación característica de asimilación (*"He interiorizado este conocimiento en la memoria del sistema..."*).
  - Si NO coincide: Metis consulta `QueryVault`, responde normalmente con contexto y **no** genera ningún archivo ni vectoriza la charla trivial.

### 3.4 Aprendizaje de Soluciones y Sesiones (`LearnFromSession`)
- **Nuevo Caso de Uso:** `backend/src/application/services/learn_from_session.py`.
- **Entrada:** `session_id`, `chat_history: list[dict]`, `solution_content: str | None`.
- **Lógica:**
  1. Filtra mensajes clave de los especialistas (Atenea, Hermes, Ícaro, Hestia, Aracne, Hefesto, Sphinx).
  2. Solicita al LLM sintetizar una ficha formal de solución arquitectónica:
     - Título y objetivo del requerimiento.
     - Decisión arquitectónica consensuada.
     - Componentes y tecnologías involucradas.
     - Lecciones aprendidas o restricciones detectadas.
  3. Almacena la nota en `vault_root/learned/{fecha}_solucion_{slug}.md` con etiquetas `[solucion, arquitectura, consenso]`.
  4. Vectoriza en ChromaDB.
- **Endpoint HTTP:** `POST /api/learning/learn-session` (con `{ session_id: str, content?: str }`).

---

## 4. Especificación Técnica Frontend

### 4.1 Soporte de Archivos en Chat
- Permitir adjuntar en el selector de archivos: `.pdf`, `.md`, `.markdown`, `.jpg`, `.jpeg`, `.png`, `.webp`.
- Reconocimiento de URLs introducidas en el input cuando se conversa con Metis.

### 4.2 Botón de Aprendizaje al Finalizar el Debate
- En el componente de mensajes del chat ([ChatPanel.vue](frontend/src/components/ChatPanel.vue)), cuando el evento o mensaje corresponda al dictamen final de Atenea o estado `done`:
  - Renderizar un botón sutil con estilo cyberpunk: `🧠 Aprender solución con Metis`.
  - Al pulsar, envía `POST /api/learning/learn-session` con feedback de éxito (*"Solución asimilada por Metis en la base de conocimiento"*).

### 4.3 Detección Conversacional en el Chat
- Si el usuario escribe a Metis *"aprende de lo hablado"* o *"aprende esto: ..."*, el backend ejecuta la asimilación y devuelve la respuesta enriquecida.

---

## 5. Plan de Ejecución TDD (Paso a Paso)

### Fase 1: Extractores Markdown e Imágenes (Backend)
1. **Test unitario:** `test_markdown_extractor.py` (parseo y lectura limpia de .md).
2. **Implementación:** `MarkdownExtractor` en `backend/src/infrastructure/learning/markdown_extractor.py`.
3. **Test unitario:** `test_image_extractor.py` (mock de llamada multimodal del LLM extrayendo descripción técnica).
4. **Implementación:** `ImageExtractor` en `backend/src/infrastructure/learning/image_extractor.py`.
5. **Ampliación de `LearnFromSource`:** soporte para `SourceType.MARKDOWN`, `SourceType.IMAGE` y `SourceType.TEXT`.

### Fase 2: Aprendizaje de Soluciones y Sesiones (Backend)
1. **Test unitario:** `test_learn_from_session.py` (validar síntesis y almacenamiento de historial en ChromaDB).
2. **Implementación:** `LearnFromSession` service.
3. **Test de integración / API:** `test_learning_routes.py` probando `POST /api/learning/learn-session`.
4. **Implementación:** Endpoint en FastAPI.

### Fase 3: Guardrail Conversacional de Metis (Backend)
1. **Actualizar `agents.yaml`:** Establecer `uses_rag: true` para Metis.
2. **Test unitario:** Validar en `test_supervisor_agent.py` o runner que la charla normal consulta RAG sin guardar, y que `"aprende esto: ..."` dispara `LearnFromSource`.
3. **Implementación:** Integración de la directiva en el flujo de chat directo con Metis.

### Fase 4: Frontend (Pinia + Vue)
1. **Test unitario:** `debate.spec.ts` validando método `learnCurrentSession()`.
2. **Implementación en `debate.ts`:** Acción `learnSession(sessionId)`.
3. **Test unitario:** `ChatPanel.spec.ts` validando renderizado del botón `Aprender solución con Metis`.
4. **Implementación en `ChatPanel.vue`:** Botón al pie de la consolidación de Atenea.

### Fase 5: Validación E2E y Sonar
1. Ejecución de suites completas (Pytest backend + Vitest frontend).
2. Comprobación de complejidad cognitiva y tipado Mypy/Vue-tsc.
