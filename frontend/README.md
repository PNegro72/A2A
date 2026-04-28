# SAPE — PWA Frontend para el Orchestrator

Interfaz web PWA para testear el sistema multi-agente de reclutamiento Accenture.
Construida con **Angular 18+**, TypeScript estricto, SCSS custom y Angular Signals.

---

## Inicio rápido

```bash
cd frontend
npm install
npm start          # http://localhost:4200
```

### Build de producción

```bash
npm run build      # genera dist/frontend/browser/
```

---

## Variables de entorno

Editá `src/environments/environment.development.ts` para dev y `src/environments/environment.ts` para prod.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `orchestratorBaseUrl` | `http://localhost:8000` | URL base del Orchestrator |
| `chatEndpoint` | `/chat` | Endpoint para iniciar un chat |
| `streamEndpoint` | `/chat/stream` | Prefijo del endpoint SSE |
| `agentName` | `Sape` | Nombre del agente en la UI |
| `agentAvatarInitials` | `H` | Iniciales del avatar del bot |
| `transportMode` | `sse` | `'sse'` o `'polling'` |
| `pollingIntervalMs` | `1000` | Intervalo de polling en ms |
| `requestTimeoutMs` | `120000` | Timeout de request en ms |

---

## Contrato esperado del back (Orchestrator)

> Para el equipo que implementa el Orchestrator.

### POST `/chat` — Iniciar mensaje

**Request:**
```json
{
  "conversation_id": "uuid-opcional-para-conv-existente",
  "message": "texto del usuario"
}
```

**Response:**
```json
{
  "conversation_id": "uuid",
  "request_id": "uuid",
  "stream_url": "/chat/stream/{request_id}"
}
```

---

### GET `/chat/stream/{request_id}` — Stream SSE

Abre una conexión Server-Sent Events. Eventos esperados:

```
event: step
data: {"agent": "job_description_agent", "status": "running", "message": "Parseando descripción..."}

event: step
data: {"agent": "internal_search_agent", "status": "done", "message": "Encontrados 12 candidatos"}

event: final
data: {"role": "assistant", "content": "Acá están los 5 mejores candidatos: ..."}

event: error
data: {"code": "AGENT_TIMEOUT", "message": "El agente tardó demasiado"}
```

`status` de pasos: `running` | `done` | `error`

---

### GET `/chat/status/{request_id}` — Polling (fallback)

Solo si `transportMode = 'polling'`.

```json
{
  "status": "running",
  "steps": [
    { "agent": "job_description_agent", "status": "done", "message": "OK", "timestamp": "..." }
  ],
  "final": null,
  "error": null
}
```

Cuando `status === "done"` incluir `final: { role: "assistant", content: "..." }`.
Cuando `status === "error"` incluir `error: { code: "...", message: "..." }`.

---

## Estructura del proyecto

```
frontend/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── models/             # message, conversation, agent-step
│   │   │   └── services/           # orchestrator, conversations, theme, config, logger
│   │   ├── features/chat/
│   │   │   ├── chat-page/          # contenedor principal
│   │   │   ├── message-list/       # lista con auto-scroll
│   │   │   ├── message-bubble/     # burbuja individual (user/bot)
│   │   │   ├── thinking-indicator/ # "Pensando..." expandible con pasos
│   │   │   ├── chat-input/         # textarea autoresize + botones
│   │   │   └── conversation-sidebar/ # drawer de conversaciones
│   │   └── shared/pipes/           # relativeTime
│   ├── environments/
│   └── styles/                     # _tokens, _themes, _mixins
├── public/
│   ├── manifest.webmanifest
│   └── icons/
├── .env.example
└── ngsw-config.json
```

---

## Deploy como PWA estática

### Nginx

```nginx
server {
  listen 80;
  root /var/www/sape/dist/frontend/browser;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location ~* \.(js|css|png|jpg|woff2)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }

  location = /ngsw-worker.js {
    expires off;
    add_header Cache-Control "no-cache";
  }
}
```

### GitHub Pages

```bash
npm run build
npx angular-cli-ghpages --dir=dist/frontend/browser
```

> Nota: el service worker no funciona en GitHub Pages sin HTTPS. Usá una URL personalizada con certificado.

---

## Tests

```bash
npm test
```

Test de ejemplo: `src/app/core/services/orchestrator.service.spec.ts`

---

## TODOs documentados

- [ ] **Virtual scroll** para conversaciones largas (>100 mensajes): usar `@angular/cdk/scrolling`.
- [ ] **Markdown rendering** en respuestas del bot: actualmente texto plano.
- [ ] **Interceptor HTTP global** de errores con toast notification.
- [ ] **CORS en el Orchestrator**: configurar `Access-Control-Allow-Origin: http://localhost:4200`.
- [ ] **Soporte a attachments** (arrastrar CVs al input).
- [ ] **Exportar conversación** como .txt o .md.
- [ ] **Autenticación SSO** si el sistema se abre más allá del equipo interno.
- [ ] **Rate limiting feedback** (429 → mostrar countdown antes de retry).
