# Agente Scheduling

Agenda reuniones y entrevistas sobre **Google Calendar** (OAuth2). Reemplaza el
workflow de n8n (`scheduling-agent-json.json`) por una implementación en
Python/Flask, manteniendo exactamente la misma interfaz A2A.

Expone dos acciones:

- **`propose_slots`** — consulta la disponibilidad (freebusy) de los participantes
  dentro de una ventana de tiempo y propone hasta 5 slots libres de la duración pedida.
- **`confirm_booking`** — crea el evento en el calendario del organizador, invita
  al resto de participantes y genera un link de Google Meet.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/scheduling-agent` | Switch por `body.action` (`propose_slots` \| `confirm_booking`) |
| `GET` | `/scheduling-agent-card` | Agent card JSON |
| `GET` | `/health` | Healthcheck |

Puerto por defecto: **8004** (configurable con `SCHEDULING_AGENT_PORT`).

## Setup

### 1. Google Cloud Console
1. Entrá a [Google Cloud Console](https://console.cloud.google.com/) → creá un proyecto.
2. Habilitá la **Google Calendar API** en *APIs & Services → Library*.
3. Creá credenciales **OAuth2** de tipo **"Desktop app"** en *APIs & Services → Credentials*.
4. Descargá el JSON y guardalo como `credentials.json` en `agente_scheduling/`.

### 2. Entorno virtual
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # en Windows: .venv\Scripts\pip install -r requirements.txt
```

### 3. Generar el token OAuth2
```bash
python setup_oauth.py
```
Abre el browser para autorizar; usá la **cuenta de Gmail del organizador** (cuyo
calendario se usa para crear los eventos). Guarda `token.json`.

### 4. Configurar variables de entorno
```bash
cp .env.example .env
```

| Variable | Default | Descripción |
|---|---|---|
| `SCHEDULING_AGENT_PORT` | `8004` | Puerto del servidor Flask |
| `GOOGLE_CREDENTIALS_FILE` | `credentials.json` | Credenciales OAuth2 (Desktop app) |
| `GOOGLE_TOKEN_FILE` | `token.json` | Token OAuth2 generado por `setup_oauth.py` |

### 5. Correr
```bash
python server.py
```

## Ejemplos

### propose_slots
```bash
curl -X POST http://localhost:8004/scheduling-agent \
  -H "Content-Type: application/json" \
  -d '{
    "action": "propose_slots",
    "participants": ["org@example.com", "cand@example.com"],
    "window": { "start": "2026-04-21T09:00:00Z", "end": "2026-04-21T18:00:00Z" },
    "duration_minutes": 30
  }'
```

### confirm_booking
```bash
curl -X POST http://localhost:8004/scheduling-agent \
  -H "Content-Type: application/json" \
  -d '{
    "action": "confirm_booking",
    "participants": ["org@example.com", "cand@example.com"],
    "chosen_slot": { "start": "2026-04-21T14:00:00Z", "end": "2026-04-21T14:30:00Z" },
    "meeting_title": "Entrevista técnica"
  }'
```

## Convenciones

- **Datetimes**: ISO 8601 UTC con sufijo `Z` (ej: `2026-04-21T14:00:00Z`).
- **participants**: array de emails, mínimo 2. El **primero** es el organizador
  (el evento se crea en su calendario); el resto son invitados.
- **Stateless**: cada request es independiente. El orchestrator es quien recuerda
  los slots propuestos para mapear referencias como "el segundo".

> **Nota:** `credentials.json` y `token.json` contienen secretos — no se commitean.
