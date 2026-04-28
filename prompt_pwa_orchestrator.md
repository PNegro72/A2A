# Prompt: PWA Angular para chat con Orchestrator (sistema multi-agente de reclutamiento)

## Contexto

Estoy desarrollando un sistema multi-agente de reclutamiento en Accenture. Los agentes
están construidos con Google ADK + Gemini en Python, y se comunican entre sí mediante
el protocolo A2A. Hay un agente **Orchestrator** que coordina al resto (Job Description
Agent, Internal Search Agent, etc.) y es el único punto de entrada desde el front.

Necesito una **PWA en Angular + TypeScript** que sirva de front para probar el sistema
completo. Es una herramienta de testing interno del equipo, no un producto final para
clientes. Va a convivir en el repo del proyecto pero en una **carpeta separada** (no
mezclada con el código de los agentes Python).

---

## Lo que tenés que crear

Una aplicación **Angular standalone (última versión estable, Angular 18+)** con
TypeScript estricto, configurada como **PWA**, que funcione como un cliente de chat
contra el Orchestrator. La idea es que sea **prolija, responsive y deployable**, con
modo claro y modo oscuro.

### Estructura del repositorio

Crear en una carpeta nueva al nivel raíz del proyecto:

```
frontend/
├── src/
│   ├── app/
│   │   ├── core/                  # servicios singleton, interceptores, guards si hicieran falta
│   │   │   ├── services/
│   │   │   │   ├── orchestrator.service.ts      # cliente HTTP/SSE
│   │   │   │   ├── conversations.service.ts     # manejo de sesiones en localStorage
│   │   │   │   ├── theme.service.ts             # claro/oscuro
│   │   │   │   └── config.service.ts            # lee variables de environment
│   │   │   └── models/
│   │   │       ├── message.model.ts
│   │   │       ├── conversation.model.ts
│   │   │       └── agent-step.model.ts
│   │   ├── features/
│   │   │   └── chat/
│   │   │       ├── chat-page/                   # contenedor principal
│   │   │       ├── message-list/
│   │   │       ├── message-bubble/              # con botón copiar y retry
│   │   │       ├── thinking-indicator/          # "pensando..." expandible con pasos
│   │   │       ├── chat-input/                  # textarea autoresize + enviar
│   │   │       └── conversation-sidebar/        # listado de conversaciones
│   │   ├── shared/
│   │   │   ├── components/                      # botones, iconos, etc.
│   │   │   └── pipes/
│   │   ├── app.component.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   ├── environments/
│   │   ├── environment.ts
│   │   └── environment.development.ts
│   ├── assets/
│   │   ├── icons/                               # íconos PWA (192, 512, maskable)
│   │   └── ...
│   ├── styles/
│   │   ├── _tokens.scss                         # variables de color, spacing, typography
│   │   ├── _themes.scss                         # tema claro y oscuro
│   │   ├── _mixins.scss
│   │   └── styles.scss                          # entry point
│   ├── index.html
│   ├── main.ts
│   └── manifest.webmanifest
├── public/
├── .env.example                                 # documentado, ver más abajo
├── angular.json
├── package.json
├── tsconfig.json
├── ngsw-config.json                             # service worker config
└── README.md                                    # cómo correr, build, deploy
```

### Stack y configuración técnica

- **Angular 18+** con componentes **standalone** (no NgModules salvo que sea
  estrictamente necesario).
- **TypeScript estricto** (`strict: true`, `strictNullChecks`, `noImplicitAny`).
- **Signals** de Angular para manejo de estado reactivo donde tenga sentido
  (mensajes, conversación activa, tema, estado de "pensando").
- **SCSS** con variables CSS custom properties para los temas (no hardcodear
  colores en componentes).
- **PWA**: `@angular/pwa` con manifest, service worker, íconos, instalable en
  móvil/tablet, funciona offline al menos para mostrar el shell.
- **HttpClient** con `provideHttpClient(withFetch())` para soportar streaming.
- Sin librerías de UI pesadas (nada de Angular Material ni PrimeNG). Quiero el
  estilo a mano con SCSS para que sea liviano y customizable.
- Permitido y recomendado: una librería pequeña para íconos (ej: `lucide-angular`)
  y nada más.

### Variables de entorno (.env / environment.ts)

Usá `environment.ts` de Angular como mecanismo principal, pero documentá un
`.env.example` con las variables que el dev tiene que setear antes del build. Como
mínimo:

```
# URL del orchestrator
ORCHESTRATOR_BASE_URL=http://localhost:8000

# Endpoints (relativos a la base)
ORCHESTRATOR_CHAT_ENDPOINT=/chat
ORCHESTRATOR_STREAM_ENDPOINT=/chat/stream

# Identidad visible del agente en la UI
AGENT_NAME=SAPE
AGENT_AVATAR_INITIALS=H

# Modo de transporte: 'sse' o 'polling'
TRANSPORT_MODE=sse

# Polling fallback (ms) - solo si TRANSPORT_MODE=polling
POLLING_INTERVAL_MS=1000

# Timeout de request (ms)
REQUEST_TIMEOUT_MS=120000
```

El `AGENT_NAME` se muestra en el header del chat, en el avatar del bot y en el
título del navegador.

---

## Comportamiento del chat

### Flujo principal

1. El usuario escribe un mensaje y lo envía.
2. El front hace un **POST** al endpoint del orchestrator con el mensaje y el
   `conversation_id` (si existe).
3. Inmediatamente, el front abre una conexión **Server-Sent Events** al endpoint
   de stream para esa request, y muestra el **indicador "pensando..."**.
4. A medida que llegan eventos por SSE, se actualiza el detalle expandible del
   indicador con los pasos intermedios.
5. Cuando llega el evento final con la respuesta completa, el indicador se
   reemplaza por la **burbuja del bot** con la respuesta.
6. Si algo falla, mostrar el error en la burbuja y exponer un **botón de retry**.

### Contrato esperado del back (documentar en el README)

Como el back todavía no está, **dejá los servicios con tipos bien definidos pero
sin implementación real (placeholders con `throw new Error('Not implemented')` o
similar)**. Documentá claramente en el README el contrato esperado para que el
equipo del orchestrator lo implemente.

Contrato propuesto:

**POST `/chat`** (request inicial)
```json
// request
{
  "conversation_id": "uuid-opcional-si-es-nueva",
  "message": "texto del usuario"
}
// response (sincrónica, devuelve un id de stream)
{
  "conversation_id": "uuid",
  "request_id": "uuid",
  "stream_url": "/chat/stream/{request_id}"
}
```

**GET `/chat/stream/{request_id}`** (SSE)

Eventos esperados:
```
event: step
data: {"agent": "job_description_agent", "status": "running", "message": "Parseando descripción..."}

event: step
data: {"agent": "internal_search_agent", "status": "running", "message": "Buscando en Workday..."}

event: step
data: {"agent": "internal_search_agent", "status": "done", "message": "Encontrados 12 candidatos"}

event: final
data: {"role": "assistant", "content": "Acá están los 5 mejores candidatos: ..."}

event: error
data: {"code": "...", "message": "..."}
```

Modelar todo esto en `agent-step.model.ts` y `message.model.ts`. El tipo
`AgentStep` debe tener al menos `agent`, `status` ('running' | 'done' | 'error'),
`message`, `timestamp`.

### Fallback a polling

Si `TRANSPORT_MODE=polling`, en lugar de abrir SSE, hacer GET a
`/chat/status/{request_id}` cada `POLLING_INTERVAL_MS` y acumular los pasos
hasta que la respuesta venga con `status: "done"`. Encapsular bien la abstracción
para que el componente de chat no sepa cuál de los dos transportes se está
usando.

### Indicador "pensando..."

- Por defecto colapsado: muestra el texto "Pensando..." con tres puntitos
  animados y, si hay un paso activo, lo muestra al lado en un texto chiquito
  (ej: "Pensando... · Buscando candidatos en Workday").
- Click en el indicador → se expande y muestra la lista de todos los pasos
  recibidos hasta el momento, con el agente, su estado (ícono ✓ si done, spinner
  si running, ✗ si error) y el mensaje.
- La animación de expandir/colapsar tiene que ser suave (transition de altura).

### Features del chat

- **Historial persistente en localStorage**: cada conversación se serializa con
  un id, título (auto-generado de los primeros 40 chars del primer mensaje del
  usuario), timestamp y array de mensajes. Versioná el schema (`{ version: 1, ...}`)
  para poder migrar después.
- **Múltiples conversaciones/sesiones**: sidebar a la izquierda (en desktop) o
  drawer (en móvil) con el listado, botón "+ Nueva conversación", y posibilidad
  de renombrar y eliminar conversaciones (con confirmación).
- **Copiar mensaje al portapapeles**: botón ícono que aparece al hacer hover
  sobre la burbuja del bot (en móvil siempre visible). Feedback visual al copiar
  (ej: el ícono cambia a check por 1.5s).
- **Retry en caso de error**: si una respuesta del bot falla, su burbuja
  muestra el error y un botón "Reintentar" que reenvía el último mensaje del
  usuario.

### Otros detalles del chat

- El input es un textarea que crece hasta un máximo (ej: 6 líneas) y luego
  scrollea internamente.
- **Enter envía**, **Shift+Enter** hace salto de línea.
- Mientras hay una respuesta en curso, el input se deshabilita y el botón de
  enviar se reemplaza por uno de **detener** (que cancela la conexión SSE y
  marca el mensaje como cancelado).
- Auto-scroll al fondo cuando llega un mensaje nuevo, **pero** si el usuario
  scrolleó hacia arriba, no forzar el scroll y mostrar un botoncito flotante
  "↓ Nuevos mensajes" para que baje cuando quiera.
- Timestamps relativos en cada mensaje ("hace 2 min"), tooltip con el absoluto.

---

## Diseño visual

### Paleta - estilo Accenture

Usá los violetas/morados característicos de Accenture (los de los PPTs del
proyecto anterior). Los tokens base:

```scss
// Tema claro
--color-primary: #A100FF;        // Accenture purple core
--color-primary-hover: #7500C0;
--color-primary-soft: #F3E5FF;   // fondos sutiles
--color-bg: #FFFFFF;
--color-surface: #F7F7FA;
--color-surface-elevated: #FFFFFF;
--color-text: #1A1A1A;
--color-text-muted: #5A5A6E;
--color-border: #E5E5EC;
--color-user-bubble: #A100FF;
--color-user-bubble-text: #FFFFFF;
--color-bot-bubble: #F3E5FF;
--color-bot-bubble-text: #1A1A1A;
--color-error: #D7263D;
--color-success: #00B37E;

// Tema oscuro
--color-primary: #C77DFF;
--color-primary-hover: #E0B0FF;
--color-primary-soft: #2A0F3D;
--color-bg: #0F0B14;
--color-surface: #1A1322;
--color-surface-elevated: #221A2D;
--color-text: #F2F2F7;
--color-text-muted: #A0A0B8;
--color-border: #2E2538;
--color-user-bubble: #A100FF;
--color-user-bubble-text: #FFFFFF;
--color-bot-bubble: #221A2D;
--color-bot-bubble-text: #F2F2F7;
```

Los podés ajustar si encontrás algo más balanceado, pero respetá la identidad
violeta de Accenture.

### Toggle de tema

- Botón en el header (sol/luna).
- Tres modos: `light`, `dark`, `system` (respeta `prefers-color-scheme`). Por
  default: `system`.
- Persistir la elección en localStorage.
- Sin flash de tema incorrecto al cargar (aplicar la clase `data-theme` en el
  `<html>` antes del bootstrap, vía script inline en `index.html`).

### Tipografía

- Sans-serif moderna del sistema: usar el stack de Inter o el system-ui:
  `-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif`.
- Tamaños: usar escala (12, 14, 16, 18, 24, 32) en variables.

### Layout responsive

- **Desktop (≥1024px)**: sidebar de conversaciones a la izquierda (~280px),
  área de chat a la derecha.
- **Tablet (768-1024px)**: sidebar colapsable en drawer.
- **Móvil (<768px)**: sidebar siempre como drawer, accesible por botón hamburguesa.
  Input fijo abajo respetando el safe area inset (`env(safe-area-inset-bottom)`).
- Burbujas con max-width responsivo (ej: 75% en desktop, 90% en móvil).
- Tocá los breakpoints: 480, 768, 1024, 1280.

### Detalles de pulido

- Bordes redondeados generosos en burbujas (ej: 16px, con la esquina cercana al
  avatar de 4px para que se vea "anclada").
- Sombras sutiles en superficies elevadas.
- Transiciones suaves (200-250ms) en hover, theme switch, etc.
- Estados de focus visibles (accesibilidad).
- Spinner custom para loading, no el default del browser.
- Empty state cuando no hay conversaciones: ilustración simple con SVG inline +
  CTA "Empezá una nueva conversación".

---

## Aspectos no funcionales

- **Accesibilidad**: roles ARIA correctos en el chat (`role="log"`,
  `aria-live="polite"` para mensajes nuevos), labels en botones de ícono,
  contraste AA mínimo en ambos temas, navegable por teclado.
- **Performance**: lazy loading de la ruta de chat si tiene sentido, virtual
  scroll si llegamos a tener conversaciones largas (>100 mensajes) — si no es
  trivial, dejalo en TODO documentado.
- **Errores**: interceptor HTTP global que mapea errores de red a mensajes
  amigables.
- **Logs**: un servicio `logger.service.ts` con niveles (debug, info, warn,
  error) que en producción solo logea warn y error.
- **Tests**: dejá al menos un test de ejemplo para el `OrchestratorService` y
  el componente principal de chat. No hace falta cobertura completa.

---

## Entregables y documentación

1. **Código completo** funcionando (que `npm install && npm start` arranque sin
   errores y muestre la UI con los placeholders del back).
2. **`README.md`** con:
   - Cómo levantar el proyecto (`npm install`, `npm start`, `npm run build`).
   - Lista de variables de entorno explicadas.
   - **Contrato esperado del back** (los endpoints, el formato de los eventos
     SSE, etc.) para que el equipo del orchestrator lo implemente.
   - Instrucciones para deploy como PWA estática (ej: en un nginx o en GitHub
     Pages).
   - TODOs pendientes documentados.
3. **`.env.example`** con todas las variables comentadas.
4. **Comentarios en el código** en español, type hints/interfaces en todo lo
   importante.

---

## Cosas importantes (no las pierdas de vista)

- Estoy en **WSL sobre Windows**, así que asegurate de que todos los paths,
  comandos y line endings funcionen ahí (LF, no CRLF).
- **No mezcles** este front con el código Python de los agentes — debe vivir
  en su propia carpeta `frontend/` con su propio `package.json`.
- Si hay alguna decisión que no está cubierta acá y que afecta significativamente
  la arquitectura o la experiencia, **paráte y preguntame antes de implementarla**.
  No asumas, no improvises en cosas grandes.
- Si encontrás algo trivial sin definir (ej: un texto de placeholder, un radio
  de borde), elegí lo que más sentido tenga y dejalo comentado con `// NOTA:`.

Cuando termines, hacé un resumen de:
1. Qué quedó implementado.
2. Qué quedó como placeholder/TODO esperando al back.
3. Qué decisiones de diseño tomaste y por qué.
4. Qué comandos correr para verificar que funciona.
