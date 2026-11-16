---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: implemented
category: enterprise
tags: [patterns, microservices, clean-architecture, docker, kubernetes]
---

# Blueprint de Microservicio Corporativo

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Topología de Capas

Todo microservicio en la empresa debe estructurarse mediante arquitectura hexagonal:
- **Capa Domain:** Entidades y puertos puros. Cero dependencias externas.
- **Capa Application:** Casos de uso y orquestación de servicios de negocio.
- **Capa Infrastructure:** Adaptadores de base de datos (PostgreSQL/Redis), clientes HTTP y brokers.
- **Capa Presentation:** Controladores API REST/gRPC y WebSockets.

---

## 2. Empaquetado y Despliegue

1. **Contenedorización Multi-Stage:** Los Dockerfiles deben usar multi-stage builds con imágenes base mínimas (`alpine` o `distroless`) para reducir la superficie de ataque.
2. **Health Checks:** Exposición obligatoria de endpoints `/health/live` y `/health/ready`.
3. **Graceful Shutdown:** Intercepción de señales `SIGTERM` cerrando conexiones activas y buffers antes de finalizar el proceso.

