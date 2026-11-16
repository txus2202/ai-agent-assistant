---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: implemented
category: enterprise
tags: [guidelines, rest, api, openapi, grpc, standards]
---

# Estándar Corporativo de Diseño de APIs (REST & gRPC)

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Reglas de Diseño REST

1. **Recursos en Plural:** `/api/v1/users`, `/api/v1/debates`, `/api/v1/domains`.
2. **Métodos HTTP Semánticos:**
   - `GET`: Idempotente y libre de efectos secundarios.
   - `POST`: Creación de nuevos recursos (debe responder `201 Created` con payload del recurso o cabecera `Location`).
   - `PUT`: Reemplazo completo del recurso.
   - `PATCH`: Modificación parcial de campos.
   - `DELETE`: Eliminación (`204 No Content` o `200 OK`).
3. **Formato de Respuestas de Error:** Todas las APIs deben retornar errores estructurados en JSON:
   ```json
   {
     "error": {
       "code": "RESOURCE_NOT_FOUND",
       "message": "El dominio solicitado no existe.",
       "details": {}
     }
   }
   ```
4. **Documentación Obligatoria:** Toda API REST debe exponer su contrato interactivo OpenAPI v3 / Swagger en `/docs`.

