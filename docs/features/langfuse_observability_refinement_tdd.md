# TDD: Plan de Pruebas Dirigidas por Tests para Refinamiento de Langfuse

## 1. Estrategia de Testing (TDD)

Siguiendo el ciclo Red-Green-Refactor:
1. **Fase Roja (RED):** Escribir tests unitarios y de integración que fallen antes de modificar el código de producción:
   - Contrato del puerto `IObservabilityService` y `TraceContext` (nuevos campos `user_id`, `tags`, método `score_trace`).
   - Pruebas del adaptador `LangfuseObservabilityAdapter` con mock client verificando que `client.trace` recibe `input`, `user_id`, `tags` y que `score_trace` invoca `lf_trace.score()` o `client.score()`.
   - Pruebas de `NoOpObservabilityService` para validar que implementa `score_trace` sin errores.
   - Pruebas en `test_debate.py` verificando que el WebSocket emite trazas enriquecidas y registra el score cuando ocurre un evento HITL.
2. **Fase Verde (GREEN):** Implementar el código mínimo necesario en:
   - `backend/src/domain/ports/observability_port.py`
   - `backend/src/infrastructure/observability/langfuse_adapter.py`
   - `backend/src/presentation/api/ws/debate.py`
3. **Fase Refactor:** Asegurar cumplimiento de SonarQube, complejidad cognitiva <= 15, tipado estricto con mypy y 100% de tests pasando.

---

## 2. Matriz de Casos de Prueba

| ID | Capa | Archivo de Test | Descripción del Escenario | Resultado Esperado |
| :--- | :--- | :--- | :--- | :--- |
| **TC-OBS-01** | Dominio | `test_observability_port.py` | `TraceContext` incluye `user_id` y `tags`. | Dataclass almacena correctamente los atributos. |
| **TC-OBS-02** | Dominio | `test_observability_port.py` | `NoOpObservabilityService` satisface protocolo con `score_trace`. | Ejecuta sin excepciones ni fallos. |
| **TC-OBS-03** | Infraestructura | `test_observability_adapter.py` | `start_trace` envía `input`, `user_id` y `tags` a `client.trace()`. | `mock_client.trace` llamado con argumentos exactos. |
| **TC-OBS-04** | Infraestructura | `test_observability_adapter.py` | `score_trace` invoca `lf_trace.score()` con nombre, valor y comentario. | `mock_trace.score` llamado con parámetros correctos. |
| **TC-OBS-05** | Infraestructura | `test_observability_adapter.py` | `score_trace` en adaptador deshabilitado o sin cliente. | No arroja error y degrada graciosamente. |
| **TC-OBS-06** | Infraestructura | `test_observability_adapter.py` | `end_trace` actualiza traza con `output` nativo. | `mock_trace.update(status=..., output=...)`. |
| **TC-WS-01** | Presentación | `test_debate.py` | Inicio de debate registra traza con tags (`agent:*`, `flow:*`) e `input`. | `observability.start_trace` invocado con tags e input del usuario. |
| **TC-WS-02** | Presentación | `test_debate.py` | Recepción de `hitl_response` registra Score en Langfuse. | `observability.score_trace` llamado con `name="hitl_decision"`. |

---

## 3. Criterios de Aceptación
1. `pytest backend/tests/` pasa al 100% sin regresiones (339+ tests).
2. Las llamadas a Langfuse no bloquean ni generan latencia perceptible en el WebSocket.
3. No hay errores de tipo con `mypy` ni infracciones de complejidad cognitiva.

