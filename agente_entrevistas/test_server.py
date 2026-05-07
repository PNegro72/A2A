"""
Script de prueba para el servidor del agente entrevistas.
Correr con el servidor levantado: python server.py
"""
import requests
import json

response = requests.post("http://localhost:8003/a2a/entrevistas", json={
    "action": "preparar_entrevista",
    "candidato_id": "uuid-test-001",
    "proceso_id": "uuid-proc-001",
    "enviar_email": True,
    "candidato": {
        "nombre": "Martina Rodríguez",
        "email": "kareninakauffmann1989@gmail.com",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Kafka", "AWS"],
        "experiencia": [
            {
                "empresa": "Mercado Pago",
                "cargo": "Backend Engineer Sr.",
                "desde": "2021-03",
                "hasta": None,
                "descripcion": "Microservicios de pagos en Python/FastAPI. +2M transacciones diarias.",
            },
            {
                "empresa": "Naranja X",
                "cargo": "Backend Developer",
                "desde": "2019-06",
                "hasta": "2021-02",
                "descripcion": "APIs REST para app móvil. Migración monolito a microservicios.",
            },
        ],
        "cv_texto": "Senior backend engineer con 7 años de experiencia en fintech.",
        "proceso_titulo": "Senior Backend Engineer - Fintech",
    }
}, timeout=120)

print(json.dumps(response.json(), indent=2))