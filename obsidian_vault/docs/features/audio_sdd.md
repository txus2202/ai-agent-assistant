---
created: 2026-10-11
updated: 2026-10-22
type: spec
phase: 5
layer: infrastructure
status: implemented
category: meta-project
tags: [sdd, audio, stt, tts, faster-whisper, kokoro, vosk, wake-word]
---

# Software Design Document (SDD) - Módulo de Audio (Fase 5)

## 1. Introducción
El módulo de audio proporciona capacidades de STT (Speech-to-Text) y TTS (Text-to-Speech) a A.T.E.N.E.A. de forma 100% local (Local-First) para asegurar la privacidad y cumplir con las restricciones del entorno (Intel N100, 12GB RAM, sin GPU dedicada).

## 2. Arquitectura (Puertos y Adaptadores)
El diseño sigue la arquitectura hexagonal definida para el proyecto:
- **Puerto de Entrada:** API REST en `src/presentation/api/routes/audio.py`.
- **Servicio de Dominio/Infraestructura:** `LocalAudioService` que implementa la interfaz (implicita/explícita) de procesamiento de audio.
- **Modelos Subyacentes:**
  - **STT:** `faster-whisper` ejecutando el modelo `base` o `small`.
  - **TTS:** `kokoro-onnx` (modelo Kokoro v1.0), altamente optimizado para ejecutarse en CPU sin dependencias complejas.

## 3. Flujo de Datos (System Sequence Diagram)

### 3.1 Transcripción (STT)
1. Frontend (`ParticleOrb.vue`) captura el flujo del micrófono mediante `MediaRecorder`.
2. Al detenerse, se empaqueta el audio en un `Blob` (`audio/webm`) y se envía vía POST a `/audio/transcribe`.
3. FastAPI inyecta el `LocalAudioService`.
4. El audio en memoria (`BytesIO`) se procesa mediante el modelo Whisper instanciado.
5. Se devuelve el texto transcrito.
6. Frontend añade el texto al `store.draftMessage`.

### 3.2 Síntesis (TTS)
1. Tras la respuesta del debate o checkpoint, Frontend invoca POST a `/audio/synthesize` enviando el texto.
2. `LocalAudioService` limpia el formato Markdown y aplica la **normalización fonética técnica** (`SpanishTechPhoneticNormalizer`) para que los tecnicismos en inglés y nombres de agentes suenen naturales en castellano.
3. Sintetiza el texto normalizado a través de `Kokoro ONNX` (usando la voz femenina `ef_dora` u otra seleccionada), guardando los frames en un buffer de memoria (`soundfile`).
4. FastAPI retorna el audio como `audio/wav`.
5. Frontend reproduce el archivo automáticamente usando la API `Audio`.

### 3.3 Normalización Fonética Técnica (Spanglish Técnico para TTS)
Para evitar que el motor fonético de Kokoro en español (`lang="es"`) lea los tecnicismos en inglés con pronunciación literal en castellano (p. ej. *pi-pe-li-ne* para `pipeline`, o *do-zer* para `docker`):
- **Componente:** `src/infrastructure/audio/phonetic_normalizer.py` (`SpanishTechPhoneticNormalizer`).
- **Mecanismo:** Diccionario compilado de expresiones regulares con límites de palabra (`\b`) que mapea términos ingleses a su representación fonética natural en castellano (ej. `pipeline` $\rightarrow$ `páiplain`, `Kubernetes` $\rightarrow$ `cubérnetes`, `pull request` $\rightarrow$ `pul ricuest`, `Sphinx` $\rightarrow$ `Esfinje`).
- **Aislamiento visual/audio:** La sustitución fonética se produce exclusivamente en la cadena enviada a Kokoro; el texto del chat, historial de persistencia y base de datos conservan la ortografía original en inglés.
- **Limpieza de Markdown:** Eliminación de encabezados (`#`), formato (`**`, `*`, `_`), enlaces (`[texto](url)` $\rightarrow$ `texto`) y bloques de código para evitar que el TTS pronuncie símbolos ortográficos o URLs.

### 3.4 Detección Dinámica de Wake-Words Multi-agente (Vosk + SubAgentProfiles)
El sistema permite invocar a cualquier agente de la cuadrilla mediante voz (p. ej. *"Sphinx, hola, ¿cómo estás?"*, *"Hestia, ¿qué opinas?"*, *"Hefesto, prepara el pipeline"*, *"Atenea, resume el debate"*):
- **Fuente de Verdad Única:** En el arranque, `WakeWordService` consulta dinámicamente `get_all_profiles()` de `src/domain/agents/sub_agent_profiles.py` sin nombres ni alias hardcodeados en el servicio de audio.
- **Alias Fonéticos en Dominio (`SubAgentProfile.phonetic_aliases`):**
  Dado que el vocabulario del modelo ligero `vosk-model-small-es-0.42` no incluye ciertos nombres mitológicos o poco comunes (como "Hestia", "Aracne" o "Metis"), el modelo los decodifica acústicamente en palabras próximas de su léxico:
  - **Hestia:** decodificada habitualmente como `"bestia"`, `"este a"` (p. ej. *"Hestia qué opinas"* $\rightarrow$ *"este a qué opinas"*), `"es tía"`, `"es día"`, `"hostia"`, `"ostia"`.
  - **Sphinx:** decodificada como `"esfinge"` o `"esfinje"`.
  - **Metis:** decodificada como `"metéis"`, `"meteis"`, `"betis"`, `"metes"`.
  - **Aracne:** decodificada como `"acné"`, `"acne"`.
  - **Ícaro:** decodificada como `"icaro"`, `"ícaro"`, `"ni caro"`.
  Cada perfil en `sub_agent_profiles.py` define una tupla inmutable `phonetic_aliases` con estas variantes, permitiendo que `WakeWordService` las indexe automáticamente al arrancar.
- **Normalización Fonética:** Las palabras clave y alias se normalizan eliminando tildes y diacríticos para asegurar coincidencias robustas con límites de palabra (`\b`).
- **Contrato WebSocket (`/ws/audio/wake-word`):**
  Al detectar el nombre o alias de un agente en el stream de audio PCM de 16kHz, el servidor emite:
  ```json
  {
    "type": "WAKE_WORD_DETECTED",
    "agent_role": "senior_architect",
    "display_name": "Hestia"
  }
  ```
- **Reacción en Frontend (`debate.ts` & `ChatPanel.vue`):**
  1. El store de Pinia recibe el evento y actualiza inmediatamente `store.selectedAgent = data.agent_role`.
  2. La interfaz de usuario (`ChatPanel.vue`) actualiza visualmente el selector y el badge al agente correspondiente.
  3. Se detiene cualquier reproducción de TTS activa (`stopTts()`) y se activa automáticamente el `MediaRecorder` en `ParticleOrb.vue`.
  4. Al finalizar de hablar y transcribirse el audio con Whisper, el mensaje se envía al backend con `target_agent: store.selectedAgent`.

### 3.5 Inyección de Contexto de Sesión Compartido (Multi-turn Context Across Agents)
Para que los agentes individuales conozcan lo debatido y conversado previamente durante la sesión:
- **Carga de Inicio (`start`):** El cliente WebSocket envía junto con `user_request` y `target_agent` una lista `history` con los mensajes recientes del chat:
  ```json
  {
    "type": "start",
    "user_request": "Sphinx, ¿qué opinas de la propuesta de Ícaro?",
    "target_agent": "the_judge",
    "history": [
      { "role": "user", "content": "..." },
      { "role": "assistant", "agent": "Ícaro", "content": "..." }
    ]
  }
  ```
- **Inyección en Prompt (`SubAgentRunner` y `SupervisorAgent`):**
  El backend formatea el historial en un bloque acotado (`## Contexto de la Sesión Previa`) intercalado entre el contexto RAG y la petición actual del usuario, truncando intervenciones muy largas para respetar la ventana de contexto y latencia en el procesador N100.

### 3.6 Comandos Vocales Human-in-the-Loop (HITL)
Durante la espera en un checkpoint HITL (`isHitlRequired = true`), el stream de audio escucha disparadores de acción ejecutiva sin necesidad de interacción táctil:
- **`approve` (Aceptar):** *"aceptar"*, *"aprobar"*, *"adelante"*, *"conforme"*, *"de acuerdo"*.
- **`reject` (Rechazar):** *"rechazar"*, *"denegar"*, *"cancela"*, *"cancelar"*, *"descarta"*, *"descartar"*.
- **`refine` (Refinar):** *"refinar"*, *"corregir"*, *"cambiar"*, *"modificar"*, *"ajustar"*. Activa automáticamente el micrófono para que el usuario dicte la enmienda o feedback.
- **`divert` (Bifurcar/Desviar):** *"desviar"*, *"bifurcar"*, *"derivar"*, *"delegar"*. Desvía el flujo del debate a los agentes seleccionados.
- **`finish` (Finalizar):** *"finalizar"*, *"terminar"*, *"concluir"*, *"fin"*. Concluye anticipadamente el debate y delega la consolidación en el supervisor.

Al detectarse uno de estos disparadores mediante `WakeWordService`, el WebSocket emite `{ "type": "HITL_VOICE_COMMAND", "command": "<accion>" }`. El store frontend ejecuta de inmediato la transición correspondiente.
- **Interrupción de TTS en comandos HITL:** Al ejecutarse cualquier comando o decisión de HITL (tanto por voz: *aprobar*, *rechazar*, *desviar*, *finalizar*, *refinar*, como por clic en los botones de la interfaz), se invoca inmediatamente `stopTts()` para que Atenea (o el agente activo) deje de hablar de inmediato, silenciando el audio en reproducción exactamente igual que el botón "Silenciar".

#### Alternancia de Selección de Agentes por Voz en HITL:
- **Con HITL Activo (`isHitlRequired = true`):** Si el usuario pronuncia el nombre o alias de un agente (ej. *"Hestia"*, *"Ícaro"*), en lugar de actuar como Wake Word para iniciar una grabación directa, el sistema conmuta (toggle) dicho agente en la lista de seleccionables de HITL (`hitlTargetAgents`).
  - Si el agente no estaba seleccionado, se añade y su chip se ilumina en la interfaz.
  - Si ya estaba seleccionado, se deselecciona.
  - El supervisor y el estado de grabación no se ven interrumpidos.
- **Sin HITL Activo (`isHitlRequired = false`):** Se mantiene el comportamiento estándar de Wake Word: selecciona el agente en el selector principal y activa la grabación de audio.

### 3.7 Comando de Silenciado Global por Voz (Wake Word de Silencio)
Disponible **en todo momento** (tanto si hay un punto de control HITL activo como si no, o durante cualquier momento del debate):
- **Disparadores de Silencio:** *"silencio"*, *"silenciar"*, *"calla"*, *"callate"*, *"cállate"*.
- **Comportamiento:**
  - `WakeWordService` detecta la palabra clave y genera un resultado con `command="silence"`.
  - El WebSocket `/ws/audio/wake-word` emite el mensaje `{ "type": "SILENCE_VOICE_COMMAND" }`.
  - El cliente frontend en `useDebateStore` intercepta el evento e invoca `stopTts()`, interrumpiendo de forma instantánea la locución de voz en curso y restableciendo el reproductor de audio, replicando exactamente el comportamiento del botón "Silenciar" del chat.


## 4. Consideraciones de Rendimiento y Hardware
El despliegue está objetivo para un **Intel N100 con 12GB RAM**:
- **STT:** `faster-whisper` usa CTranslate2, ideal para la CPU del N100 con un rendimiento rápido para modelos `base`. Se fija `language="es"` y un `initial_prompt` técnico para evitar alucinaciones idiomáticas.
- **TTS:** `kokoro-onnx` permite utilizar el estado del arte en voces (Kokoro v1.0, 82M de parámetros) consumiendo muy poca RAM y generando audio en escasos segundos (~2.4s) gracias al runtime de ONNX, sorteando la falta de GPU y los altos requisitos computacionales de alternativas más pesadas.
- **Wake-Word Vosk Multia-agente:** El modelo Vosk Small en español (~40MB RAM) procesa audio en tiempo real (< 2% CPU del N100). La derivación dinámica de palabras clave desde `sub_agent_profiles.py` se ejecuta en O(N) una sola vez al instanciar el servicio (< 0.1 ms).
- **Normalizador Fonético:** Ejecución en CPU < 0.2 ms por párrafo mediante `re.sub` compilado; huella en RAM < 15 KB (0.00% de la RAM del N100).
- **Ventana de Historial Acotada:** Se limitan a los últimos 10 mensajes truncados a 500 caracteres, consumiendo < 1500 tokens de contexto para mantener la inferencia en CPU ágil y evitar degradación de memoria.

## 5. Diseño de Componentes Frontend
- El componente `ParticleOrb.vue` alberga el botón del micrófono físico (ya existente) y orquesta la grabación en `toggleRecording()`.
- Se asocia de manera reactiva con `store.draftMessage` (Store de Pinia) para unificar la entrada de texto por teclado y por voz.
- `store.selectedAgent` centraliza el agente activo, sincronizando bidireccionalmente el selector visual de `ChatPanel.vue` y los disparadores de voz multia-agente de `ParticleOrb.vue`.

