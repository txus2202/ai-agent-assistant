---
type: note
created: 2026-11-04
tags:
  - Agentes-Agentes_y_audio.jpg
  - Agentes-Agentes_y_audio
  - AI-Agents
  - Voice-Assistant
  - FastAPI
  - Vue3
  - Speech-to-Text
  - Text-to-Speech
  - RAG
  - ChromaDB
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/f780687a_Agentes-Agentes_y_audio.jpg
---

# Arquitectura de Asistente de Voz Basado en Agentes IA

## 1. Resumen General de la Arquitectura
- Sistema interactivo web basado en voz que combina arquitectura multi-agente con un backend en FastAPI y una interfaz en Vue 3.
- El flujo transforma audio de entrada en texto mediante reconocimiento de voz y lo canaliza a un supervisor central de agentes.
- El sistema utiliza bases de conocimiento vectoriales y agentes especializados para procesar la información y responder mediante texto o voz sintética.

## 2. Componentes y Subsistemas del Frontend
- **Vue 3 SPA**: Aplicación de página única que gestiona la captura de audio y la representación visual de las respuestas.
- **Audio Input**: Periférico o interfaz de captura de voz del usuario.
- **Audio Output**: Subsistema de reproducción para las respuestas de voz sintetizadas.

## 3. Capa de API y Procesamiento de Voz
- **FastAPI Endpoint**: Punto de entrada del backend que orquesta la comunicación entre la interfaz, los servicios de transcripción y el supervisor.
- **Vosk**: Motor de reconocimiento automático de voz (Speech-to-Text) para procesar el audio de entrada.
- **Piper TTS**: Sistema de conversión de texto a voz (Text-to-Speech) para generar la salida auditiva.

## 4. Subsistema de Agentes y Gestión de Datos
- **Supervisor Agent**: Nodo central de toma de decisiones que enruta solicitudes y coordina el flujo de trabajo general.
- **Specialist Agents**: Agentes secundarios con roles específicos como arquitecto, analista crítico y documentador.
- **ChromaDB + Obsidian**: Sistema de almacenamiento híbrido que integra bases vectoriales y archivos Markdown para recuperación de información (RAG).

## 5. Flujos de Datos y Protocolos
- **Captura y Transcripción**: El audio capturado por el frontend se envía a Vosk, cuyo texto resultante llega al endpoint de FastAPI.
- **Orquestación**: El endpoint comunica la solicitud al supervisor, el cual interactúa con ChromaDB y los agentes especializados.
- **Renderizado y Respuesta**: La respuesta se actualiza en la pantalla de la interfaz o se procesa mediante Piper TTS para su reproducción auditiva.

## 6. Representación Gráfica del Sistema
- La arquitectura se estructura en tres capas principales: Frontend, Backend y Procesamiento, y el Núcleo de IA y Memoria.
- Las conexiones bidireccionales y unidireccionales permiten el intercambio fluido entre STT, agentes, bases de conocimiento y TTS.