---
created: 2026-11-14
updated: 2026-11-14
type: tfm-chapter
category: meta-project
tags: [tfm, abstract, motivation, ai-agent-assistant, atenea]
---

# Capítulo 1: Resumen Ejecutivo, Motivación y Objetivos del TFM

Volver a: [[00_meta_project/MOC_Project_TFM|📁 MOC Plataforma & TFM]]

---

## 1. Resumen Ejecutivo (Abstract)

Este Trabajo de Fin de Máster (TFM) presenta el diseño, desarrollo y validación experimental de **ai-agent-assistant**, un meta-framework declarativo para la creación y orquestación de asistentes de Inteligencia Artificial especializados mediante topologías colegiadas supervisadas (*Collegiate Multi-Agent System*), y su aplicación de referencia **ATENEA** (*Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas*).

Frente a la tendencia predominante de delegar la resolución de problemas técnicos complejos en prompts monolíticos o cadenas lineales opacas (*pipelines RAG tradicionales*), este proyecto aborda la ingeniería del software crítico desde la dialéctica: un consejo virtual compuesto por 11 especialistas autónomos (innovadores, conservadores, auditores de riesgos, ingenieros de devops, etc.) que deliberan, rebaten propuestas y alcanzan consensos balanceados bajo la estricta gobernanza de supervisión humana (*Human-in-the-Loop*).

---

## 2. Motivación y Planteamiento del Problema

El despliegue de Large Language Models (LLMs) en entornos de ingeniería de software corporativa se enfrenta actualmente a cuatro barreras estructurales:

1. **Sesgo hacia la alucinación no confrontada:** Un único modelo tiende a ser complaciente o a generar soluciones técnicas que parecen viables en apariencia pero violan restricciones de seguridad, costes o patrones arquitectónicos consolidados.
2. **Contaminación de contexto y falta de gobernanza documental:** La mayoría de sistemas RAG operan sobre carpetas planas sin discriminación de dominio, provocando que directrices internas se mezclen con documentación externa o especificaciones del propio software.
3. **Acoplamiento rígido de agentes al código:** La inmensa mayoría de arquitecturas multi-agente codifican los roles, nombres y transiciones directamente en el código fuente, imposibilitando la reutilización del motor en otros dominios sin refactorizar.
4. **Fuga de privacidad de datos:** El envío de especificaciones de sistemas propietarios a APIs de terceros sin control local de embeddings o persistencia vectorizada compromete la soberanía tecnológica corporativa.

---

## 3. Hipótesis de Investigación y Objetivos

### 3.1 Hipótesis Principal
> *"Un sistema multi-agente colegiado, desacoplado declarativamente mediante especificaciones YAML y gobernado por un árbitro supervisor con intervención humana (HITL), produce arquitecturas de software significativamente más resilientes, seguras y apegadas a los estándares empresariales que una consulta directa a un LLM monolítico."*

### 3.2 Objetivos Específicos
1. **Desarrollar un Meta-Framework Agnóstico (`ai-agent-assistant`):** Basado en Clean Architecture (Hexagonal), con inversión de dependencias estricta y verificado mediante análisis estático de AST (`test_decoupling_guard.py`).
2. **Implementar la Instanciación de Referencia (`ATENEA`):** Configurar un departamento virtual completo de arquitectura IT con 11 especialistas interconectados mediante una topología deliberativa en 4 fases.
3. **Construir una Arquitectura de Conocimiento Jerárquica y Dinámica:** Integrar un Obsidian Knowledge Vault estructurado en dominios con MOCs y aprendizaje activo supervisado por el agente Metis.
4. **Diseñar un Harness de Pruebas Continuo y Riguroso:** Implementar una suite con cobertura exhaustiva (más de 370 pruebas unitarias con Vitest/pytest y pruebas de extremo a extremo con Playwright) que valide la fiabilidad y tolerancia a fallos del sistema.
5. **Garantizar la Privacidad Local-First:** Integrar modelos de embeddings (Sentence-Transformers) y bases de datos vectoriales (ChromaDB) que se ejecuten íntegramente en local.

