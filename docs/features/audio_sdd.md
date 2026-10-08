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
2. `LocalAudioService` sintetiza el texto a través de `Kokoro ONNX` (usando la voz femenina `ef_dora` u otra seleccionada), guardando los frames en un buffer de memoria (`soundfile`).
3. FastAPI retorna el audio como `audio/wav`.
4. Frontend reproduce el archivo automáticamente usando la API `Audio`.

## 4. Consideraciones de Rendimiento y Hardware
El despliegue está objetivo para un **Intel N100 con 12GB RAM**:
- **STT:** `faster-whisper` usa CTranslate2, ideal para la CPU del N100 con un rendimiento rápido para modelos `base`.
- **TTS:** `kokoro-onnx` permite utilizar el estado del arte en voces (Kokoro v1.0, 82M de parámetros) consumiendo muy poca RAM y generando audio en escasos segundos (~2.4s) gracias al runtime de ONNX, sorteando la falta de GPU y los altos requisitos computacionales de alternativas más pesadas.

## 5. Diseño de Componentes Frontend
- El componente `ParticleOrb.vue` alberga el botón del micrófono físico (ya existente) y orquesta la grabación en `toggleRecording()`.
- Se asocia de manera reactiva con `store.draftMessage` (Store de Pinia) para unificar la entrada de texto por teclado y por voz.
