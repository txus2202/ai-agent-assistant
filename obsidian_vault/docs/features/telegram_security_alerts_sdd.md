---
created: 2026-11-22
updated: 2026-11-22
type: spec
phase: 7
layer: infrastructure
status: implemented
category: meta-project
tags: [sdd, security, telegram, alerts, audit, rate-limiting, cloudflare, authentication]
---

# Software Design Document (SDD) - Sistema de Alertas de Seguridad y Auditoría en Tiempo Real vía Telegram

## 1. Introducción y Motivación

### 1.1 Contexto
La plataforma **ATENEA** (Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas) se encuentra desplegada en un entorno de homelab (Intel N100 con 12 GB DDR5 y SSD) y expuesta a través de un dominio gestionado con Cloudflare (`mylabprojects.pro`). Los únicos usuarios autorizados del sistema son el operador principal y su profesor universitario.

### 1.2 Problema
1. Aunque Cloudflare WAF proporciona mitigación de ráfagas en el borde (*edge*), cualquier intento de fuerza bruta distribuido, ataque de diccionario lento o intento de acceso indebido alcanza el backend en `/api/auth/login` o `/api/auth/setup`.
2. El operador necesita visibilidad inmediata de quién intenta autenticarse, desde qué IP, país y dispositivo, tanto en accesos legítimos como en anomalías o bloqueos de rate limit.
3. El mecanismo de alerta no debe introducir latencia en el ciclo de vida de la petición HTTP (`0 ms` de impacto perceptible para el usuario) ni saturar la API de Telegram ante un escaneo masivo (riesgo de bloqueo o límites HTTP 429).

### 1.3 Objetivos
- **Notificación en Tiempo Real:** Disparo de alertas directas a un chat privado de Telegram para eventos críticos de autenticación.
- **Configuración Granular vía `.env`:** Activación/desactivación por variables de entorno de cada tipo de evento (éxitos, fallos, filtro de administradores, umbral de reintentos y rate limit).
- **Despacho Asíncrono Garantizado:** Ejecución desacoplada del ciclo de vida HTTP, tolerante a fallos de red y funcional incluso cuando los endpoints elevan excepciones HTTP (`401 Unauthorized`, `429 Too Many Requests`).
- **Mecanismo Anti-Spam (Throttling / Cooldown):** Silenciado y agregación de eventos repetitivos procedentes de una misma IP dentro de una ventana temporal configurable.
- **Trazabilidad Geográfica y de Red:** Resolución de la IP real del cliente y su país de origen mediante cabeceras de proxy confiable de Cloudflare (`CF-Connecting-IP` y `CF-IPCountry`).

---

## 2. Arquitectura del Sistema (Clean Architecture / Hexagonal)

Siguiendo los principios de Clean Architecture del proyecto (ADR-004), la lógica de notificación se estructura desacoplando el dominio de la tecnología de transporte concreta.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Presentation Layer                            │
│  - FastAPI Routes: /api/auth/login, /api/auth/setup                    │
│  - Dependencies: check_login_rate_limit, check_setup_rate_limit        │
│  - Helper: get_client_ip (CF-Connecting-IP), get_client_country        │
│  - Concurrencia: fire_and_forget (asyncio.Task set en event loop)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ consume
┌───────────────────────────────────▼────────────────────────────────────┐
│                             Domain Layer                               │
│  - Port: ISecurityNotifier (Protocol)                                  │
│    * notify_login_attempt(...) -> bool                                 │
│    * notify_rate_limit(...) -> bool                                    │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ implementa
┌───────────────────────────────────┴────────────────────────────────────┐
│                         Infrastructure Layer                           │
│  - TelegramSecurityNotifier (httpx.AsyncClient -> Telegram Bot API)    │
│  - Filtros declarativos: success, failure, admin-only, threshold       │
│  - Motor Anti-Spam: _last_alert_time, _suppressed_counts               │
│  - Limpieza periódica de caché para evitar fugas de memoria en RAM     │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Componentes Principales

| Componente | Capa | Ubicación | Responsabilidad |
| :--- | :--- | :--- | :--- |
| `ISecurityNotifier` | Dominio (Port) | [security_notifier.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/domain/ports/security_notifier.py) | Contrato formal para el despacho de alertas de seguridad. |
| `TelegramSecurityNotifier` | Infraestructura | [telegram_notifier.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/infrastructure/security/telegram_notifier.py) | Cliente HTTP hacia Telegram con lógica de formato HTML, filtros y throttling. |
| `Settings` | Presentación | [config.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/presentation/api/config.py) | Tipado y validación de las variables de entorno de seguridad con Pydantic v2. |
| `rate_limiter.py` | Presentación | [rate_limiter.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/presentation/api/dependencies/rate_limiter.py) | Extracción segura de `CF-Connecting-IP` y `CF-IPCountry`. |
| `auth.py` | Presentación | [auth.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/presentation/api/routes/auth.py) | Disparo no bloqueante de alertas ante eventos de autenticación. |

---

## 3. Diseño Detallado de Mecanismos Técnicos

### 3.1 Despacho Asíncrono no Bloqueante (`fire_and_forget`)
En FastAPI y Starlette, la inyección estándar de `BackgroundTasks` presenta un fallo de diseño crítico: si el handler de una ruta o dependencia eleva una `HTTPException` (por ejemplo, `401 Unauthorized` ante contraseña inválida o `429 Too Many Requests`), el middleware de manejo de excepciones de Starlette descarta la ejecución de las tareas en segundo plano.

Para garantizar que los fallos de autenticación y bloqueos de seguridad se notifiquen siempre sin penalizar el tiempo de respuesta:
1. Se implementa la función auxiliar `fire_and_forget(coro)` en [auth.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/src/presentation/api/routes/auth.py).
2. Se programa la ejecución directamente en el bucle de eventos activo mediante `loop.create_task(coro)`.
3. Se mantiene una referencia débil/fuerte en un conjunto en memoria (`_background_tasks: set[asyncio.Task]`) con callback `task.add_done_callback(_background_tasks.discard)`. Esto previene que el recolector de basura de Python 3.12+ destruya la tarea antes de completar el socket HTTP.

### 3.2 Anti-Spam y Throttling (Consolidación de Alertas)
Si un bot malicioso o script automatizado lanza cientos de peticiones de login por segundo:
- Se calcula una clave de throttling:
  - `login:fail:<client_ip>` para fallos de credenciales.
  - `login:success:<client_ip>` para accesos legítimos.
  - `ratelimit:<endpoint>:<client_ip>` para bloqueos de rate limit.
- Si `tiempo_actual - ultimo_disparo < TELEGRAM_ALERT_THROTTLE_SECONDS`:
  - Se silencia la notificación inmediata a Telegram.
  - Se incrementa el contador de alertas suprimidas `_suppressed_counts[clave] += 1`.
- Al expirar la ventana de enfriamiento y recibirse una nueva anomalía:
  - Se despacha la nueva alerta añadiendo el pie informativo:
    > *⚠️ Nota: Se han agrupado y omitido X alertas similares en los últimos Ys para evitar saturación.*
  - Se resetea el contador suprimido.
- **Recolección de Caché:** Cuando el diccionario `_last_alert_time` supera los 1.000 registros, se eliminan automáticamente entradas anteriores a $2 \times \text{cooldown}$, asegurando una huella de memoria insignificante (< 1 MB en el host N100).

### 3.3 Umbral de Intentos Fallidos (`failed_login_threshold`)
- Permite configurar si se alerta en cada intento unitario (`threshold = 1`) o si se requiere un patrón sostenido de fuerza bruta (ej. `threshold = 3`).
- Se mantiene un contador por tupla `(client_ip, username)`.
- Si el usuario finalmente introduce las credenciales correctas, el contador de fallos para ese usuario/IP se resetea inmediatamente a 0.

---

## 4. Matriz de Configuración por Variables de Entorno

Todas las variables son opcionales y disponen de valores por defecto seguros:

| Variable | Tipo | Default | Descripción |
| :--- | :--- | :--- | :--- |
| `TELEGRAM_ALERTS_ENABLED` | `bool` | `true` | Habilita o deshabilita globalmente el servicio de notificaciones. |
| `TELEGRAM_BOT_TOKEN` | `str` | `""` | Token del bot provisto por `@BotFather`. Si está vacío, el servicio se desactiva silenciosamente. |
| `TELEGRAM_CHAT_ID` | `str` | `""` | Identificador del chat o usuario destinatario provisto por `@userinfobot`. |
| `TELEGRAM_ALERT_ON_LOGIN_SUCCESS` | `bool` | `true` | Envía alertas ante inicios de sesión exitosos. |
| `TELEGRAM_ALERT_ADMIN_ONLY_SUCCESS`| `bool` | `false`| Si es `true`, solo alerta inicios de sesión con rol Administrador (👑). Si es `false`, alerta cualquier acceso. |
| `TELEGRAM_ALERT_ON_LOGIN_FAILURE` | `bool` | `true` | Envía alertas ante credenciales erróneas o cuentas inactivas. |
| `TELEGRAM_ALERT_FAILED_LOGIN_THRESHOLD`| `int` | `1` | Número mínimo de fallos consecutivos desde una IP antes de alertar por Telegram. |
| `TELEGRAM_ALERT_ON_RATE_LIMIT` | `bool` | `true` | Envía alertas cuando una IP sobrepasa el límite de peticiones (HTTP 429). |
| `TELEGRAM_ALERT_THROTTLE_SECONDS` | `int` | `60` | Segundos de enfriamiento por IP para agrupar y silenciar ráfagas de alertas idénticas. |
| `AUTH_TRUST_X_FORWARDED_FOR` | `bool` | `false`| Habilita la lectura de `CF-Connecting-IP` y `CF-IPCountry` enviados por Cloudflare. |

---

## 5. Formato de Mensajes en Telegram

Los mensajes se formatean en HTML sanitizado mediante `html.escape` para prevenir inyecciones:

### A. Acceso Exitoso (Administrador)
```html
🔐 <b>Atenea Security Alert</b>
━━━━━━━━━━━━━━━━━━━━━
<b>Evento:</b> Inicio de sesión exitoso ✅
<b>Usuario:</b> <code>jesus</code>
<b>Rol:</b> 👑 <b>Administrador</b>
<b>IP:</b> <code>85.12.34.56</code>
<b>País:</b> <code>ES</code>
<b>Fecha:</b> <code>2026-11-22 11:30:00 UTC</code>
<b>Dispositivo:</b> <i>Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...</i>
```

### B. Intento Fallido (Fuerza Bruta)
```html
🚨 <b>Atenea Security Alert</b>
━━━━━━━━━━━━━━━━━━━━━
<b>Evento:</b> Intento de inicio de sesión fallido ❌
<b>Usuario:</b> <code>root</code>
<b>IP:</b> <code>198.51.100.23</code>
<b>País:</b> <code>NL</code>
<b>Fecha:</b> <code>2026-11-22 11:30:15 UTC</code>
<b>Intentos fallidos acumulados:</b> 3
<b>Motivo:</b> Credenciales inválidas
<b>Dispositivo:</b> <i>python-requests/2.31.0</i>

⚠️ <i>Nota: Se han agrupado y omitido 2 alertas similares en los últimos 60s para evitar saturación.</i>
```

### C. Bloqueo de Rate Limit (HTTP 429)
```html
⛔ <b>Atenea Security Alert</b>
━━━━━━━━━━━━━━━━━━━━━
<b>Evento:</b> Límite de peticiones superado (HTTP 429) 🚫
<b>Endpoint:</b> <code>/api/auth/login</code>
<b>IP:</b> <code>198.51.100.23</code>
<b>País:</b> <code>NL</code>
<b>Fecha:</b> <code>2026-11-22 11:30:20 UTC</code>
```

---

## 6. Pruebas y Verificación

La implementación cuenta con una suite completa de pruebas unitarias e integración en [test_telegram_notifier.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/tests/infrastructure/security/test_telegram_notifier.py) y [test_auth.py](file:///Users/jesusjimenezvaquero/Documents/WS/ai-agent-assistant/backend/tests/presentation/api/routes/test_auth.py):

1. **Pruebas de Filtros y Configuración:**
   - Desactivación limpia sin llamadas de red si faltan credenciales o `enabled=False`.
   - Filtro de `alert_admin_only_success=True` validando omisión en usuarios estándar y alerta en administradores.
   - Umbral `failed_login_threshold=3` verificando que los intentos 1 y 2 no emiten mensaje y el 3º emite con el total acumulado.
2. **Pruebas de Throttling y Anti-Spam:**
   - Envío de primera alerta y supresión de llamadas consecutivas durante la ventana de 60 segundos.
   - Inclusión automática de la nota de alertas suprimidas tras la expiración del cooldown.
3. **Resiliencia y Tolerancia a Fallos:**
   - Respuestas HTTP de error de Telegram (`400 Bad Request`, `401 Unauthorized`) capturadas de forma segura devolviendo `False` y registrando advertencia en log sin propagar excepciones.
   - Timeouts de conexión de red simulados con `httpx.ConnectTimeout` verificando recuperación transparente.
4. **Pruebas de Integración con Rutas:**
   - Verificación de que peticiones con `CF-Connecting-IP` y `CF-IPCountry` transmiten la IP y país correctos al notificador en `200 OK`, `401 Unauthorized` y `429 Too Many Requests`.

