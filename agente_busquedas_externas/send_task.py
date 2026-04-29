"""Quick test client — sends a task to the agente_busquedas_externas A2A server."""
import json
import httpx

payload = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
        "message": {
            "role": "user",
            "messageId": "msg-001",
            "parts": [
                {
                    "text": json.dumps({
                        "job_description": (
                            "Senior Python backend engineer with FastAPI and PostgreSQL "
                            "experience, 5+ years, fully remote position."
                        ),
                        "location": "Buenos Aires",
                        "work_mode": "remote",
                    })
                }
            ],
        }
    },
}

response = httpx.post("http://localhost:8080/", json=payload, timeout=300)
print(json.dumps(response.json(), indent=2))
