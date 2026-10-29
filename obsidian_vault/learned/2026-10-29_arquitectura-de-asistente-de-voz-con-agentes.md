---
type: note
created: 2026-10-29
tags: [arquitectura, agentes, fastapI, ia, voz, c50f6d1a-8072-4c88-97cf-943747640ec7.png, c50f6d1a-8072-4c88-97cf-943747640ec7]
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/c50f6d1a-8072-4c88-97cf-943747640ec7.png
---

# Arquitectura de Asistente de Voz con Agentes

## 1. Resumen General de la Arquitectura
La aplicación interactiva basada en voz se organiza mediante un núcleo de agentes inteligentes asistidos por un backend en FastAPI. El sistema procesa entradas de audio del usuario, las transcribe, gestiona la lógica mediante agentes especializados y bases de conocimiento, y responde sintetizando la salida en voz y texto.

## 2. Capa de Presentación y Actores
* **Interfaces de Audio**: Incluye el componente de entrada de captura de voz y el componente de salida para la reproducción de audio.
* **Vue 3 SPA**: Aplicación de página única que actúa como interfaz principal, gestionando la interacción visual y el envío del audio.

## 3. Capa de Procesamiento de Voz
* **Vosk**: Motor de reconocimiento de voz (STT) empleado para transcribir el audio de entrada a texto plano.
* **Piper TTS**: Motor de síntesis de voz (Text-to-Speech) encargado de transformar las respuestas textuales en audio sintetizado para el usuario.

## 4. Backend y Orquestación de Agentes
* **FastAPI Endpoint**: Servicio backend que actúa como intermediario entre la interfaz de usuario, el motor de transcripción y el núcleo de agentes.
* **Supervisor Agent**: Nodo central de toma de decisiones que coordina las consultas, la memoria y la delegación de tareas.
* **Specialist Agents**: Subsistema compuesto por roles específicos como arquitecto, analista crítico y documentador.

## 5. Capa de Persistencia y Memoria
* **ChromaDB + Obsidian**: Base de datos vectorial combinada con un sistema de notas utilizada para la recuperación de información y el contexto documental (RAG).

## 6. Flujo de Datos y Conexiones del Sistema
* **Entrada**: El audio capturado por el usuario viaja desde la interfaz web hacia el motor Vosk para su transcripción.
* **Procesamiento**: El texto transcrito llega al backend en FastAPI y es procesado por el agente supervisor, el cual consulta la base de conocimientos y delega subtareas a los agentes especialistas.
* **Salida**: La respuesta generada se envía a Piper TTS para la conversión a audio y se actualiza la pantalla del cliente con información textual.

## 7. Diagrama de Arquitectura Mermaid
```mermaid
graph TD
    AudioInput[Audio Input] --> VueSPA[Vue 3 SPA]
    VueSPA --> AudioOutput[Audio Output]
    VueSPA -->|Envía audio de entrada| Vosk[Vosk]
    Vosk -->|Texto Transcrito| FastAPI[FastAPI Endpoint (Back)]
    FastAPI -->|Actualiza Pantalla| VueSPA
    FastAPI <--> Supervisor[Supervisor Agent]
    Supervisor <-->|Respuesta en Texto| FastAPI
    Supervisor <--> Chroma[ChromaDB + Obsidian]
    Supervisor <--> Specialists[Specialist Agents<br>- Arquitecto<br>- Analista crítico<br>- Documentador]
    Supervisor -->|Respuesta en Audio| Piper[Piper TTS]
    Piper --> VueSPA
```