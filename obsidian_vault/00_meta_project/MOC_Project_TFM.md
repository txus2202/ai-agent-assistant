---
created: 2026-11-14
updated: 2026-11-20
type: moc
category: meta-project
tags: [moc, tfm, platform, ai-agent-assistant, atenea]
---

# 📁 MOC — Plataforma & TFM (ai-agent-assistant)

Volver a: [[HOME|🏛️ HOME Master Index]]

Este Mapa de Contenido reúne la fundamentación teórica, las especificaciones funcionales y técnicas, la arquitectura de software y la estrategia de aseguramiento de calidad del **Trabajo de Fin de Máster (TFM)** en Desarrollo de Aplicaciones con IA.

---

## 🎓 Memoria Técnica del TFM

1. [[00_meta_project/tfm/01_abstract_and_motivation|01. Resumen Ejecutivo, Motivación y Objetivos]]: Justificación del paradigma multi-agente frente a modelos monolíticos, objetivos de investigación y alcance de la tesis.
2. [[00_meta_project/tfm/02_agentic_framework_vs_app|02. La Dualidad: ai-agent-assistant vs ATENEA]]: Desacoplamiento estricto entre el meta-framework generativo agnóstico y su instanciación de referencia para arquitectura IT.
3. [[00_meta_project/tfm/03_system_architecture|03. Arquitectura del Sistema]]: Clean Architecture (Hexagonal), inversión de dependencias, orquestación por eventos y topología supervisada.
4. [[00_meta_project/tfm/04_testing_and_harness|04. Harness de Pruebas y Fiabilidad]]: Estrategia de testing continuo (695 unit/integration tests, 38 E2E Playwright, AST Guard Rails y fixtures deterministas).
5. [[00_meta_project/tfm/05_conclusions_and_future|05. Conclusiones y Líneas Futuras]]: Análisis de resultados, benchmarks de latencia y trabajo futuro (orquestación distribuida, federación de grafos).
6. [[docs/architecture/ai_agent_assistant_vs_atenea_concept|Especificación Conceptual de Arquitectura: ai-agent-assistant vs ATENEA]]

---

## 📐 Especificaciones de la Plataforma (SDD & TDD)

### Fases 1–4: Fundamentos, RAG, Multi-Agente e Interfaz Base
* [[docs/features/feature_init_agent|Feature: Entidad de Dominio Agent]]
* [[docs/features/feature_task_entity|Feature: Entidad de Dominio Task]]
* [[docs/features/feature_agent_repository_port|Feature: Puerto IAgentRepository]]
* [[docs/features/feature_task_repository_port|Feature: Puerto ITaskRepository]]
* [[docs/features/feature_llm_provider_port|Feature: Puerto ILLMProvider]]
* [[docs/features/feature_document_store_port|Feature: Puerto IDocumentStore + DocumentChunk]]
* [[docs/features/feature_run_agent_task|Feature: Caso de Uso RunAgentTask]]
* [[docs/features/feature_sqlite_repositories|Feature: Repositorios SQLite (Agent & Task)]]
* [[docs/features/feature_obsidian_parser|Feature: ObsidianParser (Markdown a DocumentChunks)]]
* [[docs/features/feature_rag_ingestion|Feature: ChromaDBDocumentStore + IngestVault CLI]]
* [[docs/features/feature_query_vault|Feature: Caso de Uso QueryVault]]
* [[docs/features/feature_llm_adapters|Feature: Adaptadores LLM & LLMProviderRegistry]]
* [[docs/features/feature_learning_agent|Feature: Agente de Aprendizaje (Apprentice / Metis Base)]]
* [[docs/features/feature_sub_agents|Feature: Definición de Subagentes y SubAgentRunner]]
* [[docs/features/feature_supervisor_agent|Feature: Agente Supervisor y Flujo HITL Base]]
* [[docs/features/feature_ui_shell|Feature: UI Shell & Sistema de Diseño]]
* [[docs/features/feature_chat_ui|Feature: Chat UI, Topología de Agentes y Panel HITL]]
* [[docs/features/feature_settings|Feature: Configuración de API Keys y Modelos]]
* [[docs/features/feature_learning_ui|Feature: Interfaz de Usuario de Aprendizaje]]
* [[docs/features/feature_debate_history|Feature: Persistencia del Historial de Debates]]
* [[docs/features/feature_4_agent_config|Feature: Configuración de Modelos por Agente]]
* [[docs/features/feature_4_direct_routing|Feature: Invocación Directa de Agentes y Subida de Archivos]]
* [[docs/features/feature_4_realtime_history|Feature: Persistencia en Tiempo Real del Historial]]
* [[docs/features/particle-orb|Feature: Orbe Cósmico de Partículas (ParticleOrb.vue)]]
* [[docs/features/feature_dynamic_knowledge_domains|Feature: Dominios Dinámicos y Gobernanza de Conocimiento]]

### Fases 5–7: Voz, Observabilidad, Topología Declarativa, Seguridad y E2E
* [[docs/features/audio_sdd|SDD: Módulo de Audio Local (Faster-Whisper, Kokoro TTS y Vosk Wake-Word)]]
* [[docs/features/chat_session_sdd|SDD: Sesión Continua de Chat Multi-Agente (Multi-turn)]]
* [[docs/features/supervisor_hitl_sdd|SDD: Supervisor Adaptativo & Flujo HITL Integrado]]
* [[docs/features/agent_identity_and_dynamic_checkpoints_sdd|SDD: Unificación de Identidad por display_name y Checkpoints Dinámicos]]
* [[docs/features/debate_topology_and_supervisor_discovery_sdd|SDD: Topología Declarativa del Debate y Registro Dinámico de Agentes]]
* [[docs/features/dynamic_orchestration_and_topology_view_sdd|SDD: Orquestación Dinámica por Delegación y Visualización del Consejo]]
* [[docs/features/diagram_modal_and_tts_filter_sdd|SDD: Filtro TTS de Diagramas y Visualizador Modal Mermaid]]
* [[docs/features/metis_multisource_learning_and_rag_sdd|SDD: Aprendizaje Multi-Fuente y Memoria Persistente con Metis]]
* [[docs/features/vault_sync_and_orphan_cleanup_sdd|SDD: Sincronización del Vault y Limpieza de Huérfanos en ChromaDB]]
* [[docs/features/feature_observability|SDD: Observabilidad Full-Stack con Langfuse & Mission-Control UI]]
* [[docs/features/langfuse_observability_refinement_sdd|SDD: Refinamiento Integral de Métricas y Trazabilidad en Langfuse]] · [[docs/features/langfuse_observability_refinement_tdd|TDD Plan]]
* [[docs/features/fidias_image_generation_and_modular_tools_sdd|SDD: Herramientas Modulares de Agentes, Fídias y Visualizadores Interactivos]]
* [[docs/features/html_preview_security_and_mime_types_sdd|SDD: Previsualización Segura de HTML5 en Sandbox y Tipos MIME]]
* [[docs/features/feature_authentication|SDD: Autenticación, Autorización y Gestión de Usuarios (Fase 7)]]
* [[docs/features/per_agent_rag_config_sdd|SDD: Configuración Dinámica de Recuperación RAG por Agente y Usuario]] · [[docs/features/per_agent_rag_config_tdd|TDD Plan]]
* [[docs/features/dynamic_model_probing_and_caching_sdd|SDD: Sondeo No Bloqueante (SWR) de Modelos y Caché 24h]] · [[docs/features/dynamic_model_probing_and_caching_tdd|TDD Plan]]
* [[docs/features/shared_database_model_cache_sdd|SDD: Caché Compartida de Modelos en Base de Datos y Lock Distribuido]] · [[docs/features/shared_database_model_cache_tdd|TDD Plan]]
* [[docs/features/playwright_e2e_testing_suite_sdd|SDD: Suite de Pruebas End-to-End (E2E) con Playwright]] · [[docs/features/playwright_e2e_testing_suite_tdd|TDD Plan]]

---

## 🛡️ Decisiones de Arquitectura de la Plataforma (Platform ADRs)
* [[DECISIONS|Historial General de Decisiones (ADRs 001 al 021)]]

