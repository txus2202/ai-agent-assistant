---
created: 2026-11-14
updated: 2026-11-14
type: standard
status: implemented
category: enterprise
tags: [observability, opentelemetry, tracing, metrics, logging]
---

# Estándares Corporativos de Observabilidad y Telemetría

Volver a: [[01_enterprise_architecture/MOC_Enterprise_Architecture|🏢 MOC Arquitectura Empresarial]]

---

## 1. Los Tres Pilares de Observabilidad

1. **Trazas Distribuidas (Distributed Tracing):**
   - Estándar obligatorio: **OpenTelemetry (OTel)**.
   - Todo flujo que atraviese el frontend, backend y LLMs debe propagar una cabecera de correlación (`x-trace-id` o `traceparent`).
2. **Métricas Estructuradas:**
   - Métricas de latencia p50, p95, p99.
   - Contador de tokens de entrada/salida y coste económico por modelo de IA.
   - Puntuación de calidad de respuestas y tasa de aprobación HITL (`score_trace`).
3. **Logs Estructurados (JSON):**
   - Prohibido el uso de `print` desestructurado en producción.
   - Formato JSON con campos mínimos: `timestamp`, `level`, `trace_id`, `service`, `message`.

