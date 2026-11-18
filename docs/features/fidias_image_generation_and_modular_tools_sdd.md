# SDD: Herramientas Modulares de Agentes, Generación Visual Dual para Fídias y Visualizadores Interactivos

## 1. Contexto y Objetivos

Con la evolución del consejo técnico de Atenea y la incorporación de los nuevos agentes especialistas (**Fídias**, diseñador UX/UI; **Dédalo**, desarrollador full-stack; y **Calíope**, documentadora técnica), surgió la necesidad de dotar al sistema de:
1. **Herramientas de visualización y exportación enriquecidas en la interfaz**: Visores interactivos modulares con modales a pantalla completa, copia al portapapeles y descargas con extensiones adecuadas (.md, .svg, .js, .vue, .go, .html, .png, .pdf).
2. **Capacidad de generación de imágenes reales para Fídias**: Los modelos LLM de lenguaje generan texto pero no archivos binarios de imagen. Fídias requería un mecanismo para generar imágenes reales mediante proveedores de difusión o, en su defecto, producir maquetaciones completas en HTML5/CSS semántico.
3. **Aislamiento de documentos técnicos para Calíope**: Evitar que el preámbulo o saludos conversacionales se mezclen con el documento técnico descargable (.md / .pdf), dotando a la tarjeta de documentación de scroll propio para no saturar el chat.
4. **Traducción visual a Mermaid para Metis**: Permitir que cuando Metis aprenda de imágenes o diagramas técnicos, traduzca la estructura visual a bloques ````mermaid para su persistencia en el vault y posterior renderizado interactivo en el chat.

### Objetivos Clave
- **Generación Visual Privada y de Alta Fidelidad (Fídias):**
  - **Google Imagen 3 (`imagen-3.0-generate-002`):** Motor empresarial privado vía Google GenAI SDK con alta fidelidad gráfica y privacidad garantizada bajo API empresarial (sin almacenamiento ni entrenamiento con datos de usuario).
  - **Deprecación de Proveedores Públicos (Pollinations / Flux):** Descartados y eliminados por dos motivos fundamentales: calidad visual insuficiente y pérdida del aislamiento de privacidad que caracteriza a Atenea (servicios públicos gratuitos que enrutan o exponen prompts en internet).
  - **Fallback Automático:** Si no se define proveedor (`IMAGE_GENERATION_PROVIDER=""` o `"none"`), Fídias genera una maquetación completa en HTML5 semántico con CSS moderno embebido y vanilla JS dentro de un bloque ````html````.
- **Herramientas Modulares de UI (`frontend/src/components/tools/`):**
  - `CodeModal.vue`: Editor de solo lectura con numeración de líneas, selector de lenguaje, copia y descarga dinámica (.js, .html, .py, etc.).
  - `DiagramModal.vue`: Renderizador vectorial interactivo de Mermaid con zoom/pan, descarga SVG y copia de sintaxis.
  - `DocumentModal.vue`: Visor de documentos técnicos con pestañas de vista previa renderizada y código Markdown raw, copia, descarga `.md` y exportación limpia a PDF.
  - `ImageModal.vue`: Visor de imágenes rasterizadas con controles de zoom (100% a 300%), copia de URL y descarga directa en PNG.
  - Botones icon-only con tooltips flotantes en hover en todas las tarjetas y modales.

---

## 2. Arquitectura de la Solución

```mermaid
flowchart TD
    subgraph Client ["Frontend (Vue 3 / ChatPanel.vue)"]
        A[Mensaje del Asistente] --> B[parseMessageContent / messageParser.ts]
        B -->|Bloque Texto| C[Párrafo Estilizado]
        B -->|Bloque Mermaid| D[Tarjeta Diagrama -> DiagramModal]
        B -->|Bloque Code| E[Tarjeta Código -> CodeModal]
        B -->|Bloque Document| F[Tarjeta Documento -> DocumentModal]
        B -->|Bloque Image| G[Tarjeta Imagen -> ImageModal]
    end

    subgraph Backend ["Backend (FastAPI / SubAgentRunner)"]
        H[User Request a Fídias] --> I{IMAGE_GENERATION_PROVIDER?}
        I -->|imagen| K[Inyecta Directiva Generación Imagen 3]
        I -->|none / vacío| L[Inyecta Directiva Maquetación HTML5/CSS]
        
        K --> M[LLM Output con GENERATE_IMAGE: prompt]
        L --> N[LLM Output con bloque html]

        M --> O[ImageGenerationService.generate_and_save]
        O --> P[(Almacenamiento Local /tmp/atenea_images)]
        O --> Q[Reemplaza directiva por ![Diseño](/api/images/filename.png)]
    end

    subgraph API ["Endpoints de Imágenes"]
        P --> R[GET /images/filename]
        P --> S[GET /api/images/filename]
    end

    Q --> A
    N --> A
    G -->|Petición de imagen| R
```

---

## 3. Especificación Técnica por Capas

### A. Capa de Dominio (`backend/src/domain/`)
- **`agents.yaml`:**
  - Registro de Fídias con herramientas `[code_viewer, image_viewer]`.
  - Instrucciones explícitas de comportamiento condicional según la variable `IMAGE_GENERATION_PROVIDER`.
  - Registro de Calíope con herramienta `[document_viewer]` y regla estricta de aislamiento del documento técnico en bloque Markdown.
  - Registro de Metis con herramienta `[diagram_viewer]` y directiva de emisión de bloques Mermaid al consultar conocimiento aprendido de esquemas visuales.

### B. Capa de Aplicación (`backend/src/application/`)
- **`sub_agent_runner.py`:**
  1. **Inyección Dinámica de Directivas:** Antes de invocar al LLM para Fídias, consulta el proveedor activo mediante `ImageGenerationService.get_provider_name()`.
     - Si hay proveedor activo: Inyecta la directiva obligatoria `[GENERATE_IMAGE: <prompt en inglés>]`.
     - Si no hay proveedor: Inyecta la directiva de maquetación visual completa en HTML5 semántico con estilos y scripts integrados.
  2. **Post-procesamiento y Sustitución de Directivas:** Al recibir la respuesta del LLM:
     - Detecta patrones `\[GENERATE_IMAGE:\s*(.+?)\]` o `<!--\s*generate_image:\s*(.+?)\s*-->`.
     - Invoca asíncronamente `ImageGenerationService.generate_and_save(prompt, provider)`.
     - Reemplaza la directiva por la sintaxis Markdown `![alt](/api/images/{filename})`.
     - Si la generación falla (p.ej. timeout o cuota excedida), inserta una nota de aviso elegante sin interrumpir el debate ni arrojar error 500.

### C. Capa de Infraestructura (`backend/src/infrastructure/image_generation/`)
- **`service.py`:**
  - `ImageGenerationService`:
    - `get_provider_name() -> str | None`: Resuelve el proveedor desde `Settings.image_generation_provider` y variables de entorno (`IMAGE_GENERATION_PROVIDER`, `IMAGE_PROVIDER`), aceptando únicamente motores privados (`imagen`).
    - `generate_and_save(prompt: str, provider: str) -> tuple[str, str]`: Genera los bytes y los guarda con nombre único `fidias_{uuid}.png` en el directorio de almacenamiento.
    - `get_image_path(filename: str) -> Path | None`: Valida que el archivo exista dentro del directorio permitido, sanitizando contra ataques de *directory traversal* (`../`).
  - `ImagenGenerator`: Cliente `google.genai` que invoca `models.generate_images(model="imagen-3.0-generate-002", ...)`.

### D. Capa de Presentación (`backend/src/presentation/api/`)
- **`config.py`:**
  - Campo `image_generation_provider: str = ""` en `Settings` con carga automática desde `.env` y variables de entorno del sistema.
- **`routes/images.py`:**
  - Endpoints `GET /images/{filename}` y `GET /api/images/{filename}` para servir los archivos binarios de forma segura con cabeceras `Content-Type` adecuadas.
- **`app.py`:**
  - Inclusión del router `images.router` en la factoría de la aplicación FastAPI.

### E. Frontend (`frontend/src/`)
- **`utils/messageParser.ts`:**
  - Parser multiformato que divide el contenido del mensaje en bloques secuenciales: `text`, `mermaid`, `code`, `document` e `image`.
- **`components/tools/`:**
  - Componentes modulares independientes para cada tipo de recurso interactivo (`CodeModal`, `DiagramModal`, `DocumentModal`, `ImageModal`).
- **`components/ChatPanel.vue`:**
  - Renderizado condicional de tarjetas temáticas con scroll interno acotado (`max-h-56` para código y documentos), botones icon-only con tooltips descriptivos en hover, y apertura de modales completas.

### F. Política Universal de Silencio de Herramientas en Voz y TTS (`ttsFilter.ts` y `debate.ts`)
- **Regla Estricta:** Ningún agente leerá jamás en voz alta el contenido interno de una herramienta (bloques de código HTML5/CSS/JS, Python, Go, diagramas Mermaid, actas/documentos Markdown completos, ni directivas de imagen `[GENERATE_IMAGE: ...]`).
- **Filtrado en Streaming (`feedTtsStreamingChunk` en `debate.ts`):**
  - Mantiene una máquina de estados que detecta la apertura de cercas (` ``` `).
  - Mientras `isInsideCodeFence` está activo, todo el contenido de la herramienta se silencia y descarta del búfer de TTS.
  - Al cerrarse la cerca (` ``` `), se reanuda la escucha de texto conversacional normal.
- **Filtrado de Mensajes Completos (`cleanTextForTts` en `ttsFilter.ts`):**
  - Remueve todos los bloques delimitados por ````...````, imágenes Markdown `![alt](url)` y directivas `[GENERATE_IMAGE: ...]`.
  - Si el mensaje contiene explicaciones antes o después de la herramienta, sintetiza fluidamente únicamente dichas explicaciones.
  - Si el mensaje consiste **exclusivamente en la herramienta**, emite una locución sustituta natural y breve según el tipo:
    - Código (HTML/JS/Python): `"He generado el código en pantalla."`
    - Diagrama Mermaid: `"He generado el diagrama arquitectónico en pantalla."`
    - Documento técnico (Markdown/Doc): `"He generado el documento técnico en pantalla."`
    - Imagen rasterizada: `"He generado la imagen en pantalla."`
- **Saneamiento en Backend (`SpanishTechPhoneticNormalizer`):**
  - En [`phonetic_normalizer.py`](backend/src/infrastructure/audio/phonetic_normalizer.py), `strip_markdown()` elimina por completo bloques ````...````, enlaces de imagen y directivas `GENERATE_IMAGE`, garantizando que la síntesis local por Kokoro permanezca 100% limpia de sintaxis técnica.

---

## 4. Configuración y Despliegue en Entornos (Docker / N100)

1. **Variables de Entorno (`.env`):**
   ```bash
   # Proveedor comercial privado Google Imagen 3 (requiere GEMINI_API_KEY)
   IMAGE_GENERATION_PROVIDER=imagen
   
   # O sin generador (fallback a maquetación HTML5 completa y segura)
   # IMAGE_GENERATION_PROVIDER=none
   ```
2. **Propagación en `docker-compose.yml`:**
   El contenedor `backend` expone explícitamente:
   ```yaml
   environment:
     - IMAGE_GENERATION_PROVIDER=${IMAGE_GENERATION_PROVIDER:-}
   ```
3. **Reconstrucción de Contenedores:**
   Dado que el servicio de generación de imágenes y las nuevas rutas son código compilado en la imagen Docker del backend, cualquier actualización requiere:
   ```bash
   docker compose up -d --build
   ```

---

## 5. Estrategia de Pruebas (TDD)

### Backend Tests
- `backend/tests/infrastructure/test_image_generation.py`:
  - Normalización y rechazo de motores públicos no confiables (`pollinations` -> `None`).
  - Activación exclusiva de Google Imagen 3 (`imagen`, `google`).
  - Generación simulada con Imagen 3 y validación de llamadas SDK.
  - Almacenamiento seguro en disco y prevención de *path traversal*.
- `backend/tests/presentation/api/routes/test_images.py`:
  - Servicio exitoso de imágenes vía `GET /images/{filename}` y `GET /api/images/{filename}`.
  - Respuestas 404 para archivos inexistentes y 400 para nombres inválidos.
- `backend/tests/application/agents/test_sub_agent_runner.py`:
  - Inyección de directiva HTML5 cuando no hay proveedor configurado.
  - Intercepción de `[GENERATE_IMAGE: ...]` y reemplazo por enlace markdown cuando el proveedor está activo.
  - Sustitución elegante por mensaje de aviso cuando el proveedor arroja error.

### Frontend Tests
- `frontend/src/utils/__tests__/messageParser.spec.ts`:
  - Extracción precisa de bloques de imagen `![alt](url)`, bloques de código, documentos y diagramas.
- `frontend/src/components/tools/__tests__/ImageModal.spec.ts`:
  - Apertura de modal con imagen, zoom (in, out, reset), copia de URL y cierre.
- `frontend/src/components/tools/__tests__/DocumentModal.spec.ts` & `CodeModal.spec.ts`:
  - Renderizado de pestañas, numeración de líneas, copia y descarga con extensiones adecuadas.
- `frontend/src/components/__tests__/ChatPanel.spec.ts`:
  - Renderizado de tarjetas de imagen, código y documentos con botones de visualización y descarga.

