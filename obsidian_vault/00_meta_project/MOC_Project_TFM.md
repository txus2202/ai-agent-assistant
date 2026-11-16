---
created: 2026-11-14
updated: 2026-11-14
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
4. [[00_meta_project/tfm/04_testing_and_harness|04. Harness de Pruebas y Fiabilidad]]: Estrategia de testing continuo (377 unit tests, 38 E2E Playwright, AST Guard Rails y fixtures deterministas).
5. [[00_meta_project/tfm/05_conclusions_and_future|05. Conclusiones y Líneas Futuras]]: Análisis de resultados, benchmarks de latencia y trabajo futuro (orquestación distribuida, federación de grafos).

---

## 📐 Especificaciones de la Plataforma (SDD)

* [[docs/features/feature_dynamic_knowledge_domains|Feature: Dominios Dinámicos y Gobernanza de Conocimiento]]
* [[docs/features/feature_4_agent_config|Feature: Configuración Declarativa de Agentes (agents.yaml)]]
* [[docs/features/feature_supervisor_agent|Feature: Agente Supervisor y Deliberación Colegiada]]
* [[docs/features/feature_learning_agent|Feature: Agente de Aprendizaje (Metis) y RAG Multimodal]]
* [[docs/features/feature_rag_ingestion|Feature: Ingesta Recursiva y Vectorización ChromaDB]]
* [[docs/features/feature_debate_history|Feature: Persistencia SQLite de Historiales de Sesión]]
* [[docs/features/feature_chat_ui|Feature: Interfaz Reactiva Vue 3 con Feedback Multimodal]]

---

## 🛡️ Decisiones de Arquitectura de la Plataforma (Platform ADRs)
* [[DECISIONS|Historial General de Decisiones (ADRs 001 al 014)]]

