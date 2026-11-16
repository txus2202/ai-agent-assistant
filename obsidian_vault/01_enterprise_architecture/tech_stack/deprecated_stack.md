---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: deprecated
category: enterprise
tags: [tech-stack, deprecated, legacy, migration, sphinx]
---

# Catálogo de Tecnologías Desaconsejadas y en Retirada

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Tecnologías Bloqueadas para Nuevos Desarrollos

Cualquier propuesta que pretenda introducir o ampliar el uso de las siguientes tecnologías será vetada por la auditoría técnica de **Sphinx**:

1. **PHP < 8.2 y frameworks legacy (CodeIgniter, CakePHP):** En fase de migración activa.
2. **MongoDB sin transacciones multi-documento:** Se prohíbe para datos financieros o transaccionales críticos (usar PostgreSQL con JSONB).
3. **SOAP / XML Web Services:** Prohibido para nuevas integraciones (utilizar REST OpenAPI v3 o gRPC).
4. **RabbitMQ autogestionado en VMs:** Sustituido por Google Cloud Pub/Sub o Kafka gestionado para reducir overhead operacional.
5. **Autenticación Stateful basada en sesiones en memoria de proceso único:** Prohibida para microservicios horizontales.

