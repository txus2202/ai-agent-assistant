---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: implemented
category: enterprise
tags: [tech-stack, approved, backend, frontend, database, cloud, hestia]
---

# Catálogo de Tecnologías Aprobadas por la Organización

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Principio Rector

Toda nueva propuesta técnica en la organización debe alinearse de forma prioritaria con las tecnologías recogidas en este catálogo. La incorporación de herramientas no listadas requiere la justificación de un ADR específico evaluado por el consejo de arquitectura.

---

## 2. Lenguajes y Runtimes de Backend

| Tecnología | Versión Mínima | Ámbito de Aplicación | Justificación |
| :--- | :--- | :--- | :--- |
| **Python** | 3.12+ (LTS) | Microservicios de IA, orquestación, APIs REST ligeras | Ecosistema de machine learning, rapidez de entrega y tipado estricto con Pydantic. |
| **Go** | 1.22+ | Servicios de alto rendimiento, proxies, gateways de red | Baja latencia, concurrencia nativa (goroutines) y bajo consumo de memoria. |
| **Node.js / TypeScript** | 20+ LTS | BFFs (Backend for Frontend), servicios de agregación | Compartición de modelos de datos con el frontend. |

---

## 3. Frontend y Aplicaciones Web

| Tecnología | Versión | Ámbito |
| :--- | :--- | :--- |
| **Vue 3 + TypeScript** | 3.4+ / Composition API | SPAs corporativas, dashboards internos y herramientas operativas. |
| **Pinia** | 2.1+ | Gestión de estado centralizado y reactivo. |
| **Tailwind CSS** | 3.4+ | Sistema de diseño atómico y coherencia visual corporativa. |

---

## 4. Persistencia y Bases de Datos

| Motor | Tipo | Caso de Uso Oficial |
| :--- | :--- | :--- |
| **PostgreSQL** | Relacional (ACID) | Almacenamiento transaccional principal de la empresa (Cloud SQL / RDS). |
| **ChromaDB / Qdrant** | Vector Store | Búsqueda semántica, RAG y memoria de asistentes IA locales/híbridos. |
| **Redis** | In-Memory Key-Value | Caché distribuida de sesión y rate-limiting. |

---

## 5. Mensajería y Eventos

* **Google Cloud Pub/Sub / Apache Kafka:** Broker corporativo oficial para arquitecturas basadas en eventos y comunicación desacoplada.
* **Google Cloud Tasks:** Encolamiento y ejecución de tareas asíncronas con reintentos configurables.

