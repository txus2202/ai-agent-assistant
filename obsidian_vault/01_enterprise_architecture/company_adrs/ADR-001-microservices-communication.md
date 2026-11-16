---
created: 2026-11-14
updated: 2026-11-14
type: adr
status: accepted
category: enterprise
tags: [adr, microservices, pubsub, grpc, rest, hestia, sphinx]
---

# ADR-001: Estrategia de Comunicación Inter-Servicios (Síncrona vs Asíncrona)

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Contexto

Con la expansión de la arquitectura de microservicios en la organización, varios equipos estaban implementando llamadas HTTP REST síncronas encadenadas (HTTP cascading), lo que generaba acoplamiento temporal, aumento de latencia acumulada y puntos únicos de fallo en cascada.

---

## 2. Decisión

1. **Comunicación Asíncrona por Defecto:** Toda comunicación entre microservicios que no requiera respuesta inmediata para el usuario final debe realizarse de forma asíncrona mediante eventos a través de **Google Cloud Pub/Sub** o **Kafka**.
2. **Uso Restringido de Comunicación Síncrona:** Las llamadas síncronas se limitan estrictamente a consultas de lectura en tiempo real mediante **gRPC** o REST con circuit breakers implementados obligatoriamente.
3. **Idempotencia:** Todos los consumidores de eventos deben implementar deduplicación de mensajes mediante claves de idempotencia persistidas en Redis o PostgreSQL.

---

## 3. Consecuencias y Auditoría

* **Hestia:** Toda nueva propuesta técnica debe justificar cualquier llamada síncrona inter-servicios.
* **Sphinx:** Si una propuesta incluye llamadas HTTP encadenadas en cascada, se emitirá una objeción de riesgo alto.

