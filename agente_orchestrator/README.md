# Recruiting Orchestrator

Central coordinator of the A2A recruiting system. Receives requests from a recruiter and delegates them to specialized agents via HTTP.

## Requirements

- Python 3.11+
- An OpenAI API key

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file in this folder (never commit it):

```env
OPENAI_API_KEY=sk-...

SCHEDULING_AGENT_WEBHOOK_URL=https://<your-n8n-instance>/webhook/scheduling-agent
SCHEDULING_AGENT_CARD_URL=https://<your-n8n-instance>/webhook/scheduling-agent-card

RECRUITER_EMAIL=your-email@example.com
DEFAULT_TIMEZONE=America/Argentina/Buenos_Aires
```

## Run

From inside the `orchestrator/` folder:

```bash
python main.py
```

Type `exit` or `quit` to stop the session.

## Adding a new agent

1. Append an entry to `registry/registry.json`
2. Add the agent's card URL env var to `.env`
3. Optionally add a fallback card under `registry/fallback_cards/`
4. Restart the orchestrator — no Python changes required
