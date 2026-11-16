---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: implemented
category: enterprise
tags: [security, oauth2, oidc, pii, gdpr, rbac, encryption]
---

# Directrices Corporativas de Ciberseguridad, Identidad y PII

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Identidad y Control de Acceso (IAM)

1. **Protocolo Central:** OpenID Connect (OIDC) y OAuth 2.0 con tokens JWT firmados con algoritmos seguros (RS256 o EdDSA; HMAC-SHA256 permitido para desarrollo local con secretos de alta entropía).
2. **Políticas de Cookies:** Las cookies de sesión deben tener estrictamente `HttpOnly; Secure; SameSite=Strict`.
3. **Hashing de Contraseñas:** Algoritmo oficial obligatorio: **Argon2id** (o bcrypt con factor de coste >= 12 si Argon2id no está soportado en la plataforma).

---

## 2. Privacidad y Protección de Datos Personales (GDPR)

1. **Aislamiento por Usuario (Tenant/User Isolation):** Todo recurso, debate o historial persistido en bases de datos debe estar indexado y filtrado por `user_id`.
2. **Prohibición de Datos PII en LLMs Externos:** Queda terminantemente prohibido enviar información personal identifiable (nombres de clientes, tarjetas, datos de salud) a proveedores LLM en la nube pública sin anonimización o consentimiento explícito.
3. **Cifrado Obligatorio:** Datos en tránsito siempre bajo TLS 1.3; datos en reposo cifrados mediante AES-256 en discos y buckets de Cloud.

