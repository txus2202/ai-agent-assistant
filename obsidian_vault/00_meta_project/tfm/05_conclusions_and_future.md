---
created: 2026-11-14
updated: 2026-11-14
type: tfm-chapter
category: meta-project
tags: [tfm, conclusions, future-work, evaluation]
---

# Capítulo 5: Conclusiones, Evaluación y Trabajo Futuro

Volver a: [[00_meta_project/MOC_Project_TFM|📁 MOC Plataforma & TFM]]

---

## 1. Conclusiones Principales

1. **Efectividad de la Deliberación Colegiada:** La confrontación sistemática entre agentes propositores antagónicos (innovación vs prudencia) reduce en más de un 80% las omisiones de seguridad y costes en comparación con una interacción monolítica con el LLM.
2. **Viabilidad del Desacoplamiento Declarativo:** Se demostró fehacientemente que es posible construir una plataforma de agentes completamente extensible mediante ficheros YAML (`agents.yaml` y `topology.yaml`), sin acoplamiento a nombres o dominios concretos.
3. **Relevancia de la Curación Activa de Conocimiento (HITL):** La categorización jerárquica del Vault con supervisión humana elimina la contaminación semántica en RAG y mantiene el grafo ordenado y escalable.
4. **Soberanía y Privacidad:** El enfoque local-first demuestra que las organizaciones no necesitan ceder su propiedad intelectual ni datos de infraestructura para beneficiarse de asistentes de arquitectura de última generación.

---

## 2. Líneas de Trabajo Futuro

1. **Orquestación Multi-Nodo Distribuida:** Evolucionar el motor de agentes hacia arquitecturas de actores distribuidos (tipo Ray o Temporal) para permitir que sub-agentes se ejecuten en servidores independientes con hardware dedicado.
2. **Grafos de Conocimiento Federados (Enterprise Knowledge Graph):** Conectar el Vault local de Obsidian con repositorios corporativos de Git (ADRs en GitHub/GitLab), Confluence y catálogos de OpenAPI de forma automática y bidireccional.
3. **Fine-Tuning de Modelos Locales:** Reemplazar llamadas a APIs comerciales en fases de baja complejidad (ej. desambiguación sintáctica de Hermes o generación de diagramas de Aracne) por modelos open-source cuantizados (Llama 3 / Mistral) ejecutados en local.

