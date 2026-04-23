import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

os.environ.setdefault("GOOGLE_API_KEY",       "test-google-key")
os.environ.setdefault("SUPABASE_URL",         "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("TAVILY_API_KEY",       "test-tavily-key")
os.environ.setdefault("KIT_OUTPUT_DIR",       "/tmp/test_kits")
os.environ.setdefault("MS_TENANT_ID",         "test-tenant")
os.environ.setdefault("MS_CLIENT_ID",         "test-client-id")
os.environ.setdefault("MS_CLIENT_SECRET",     "test-secret")
os.environ.setdefault("MS_SENDER_EMAIL",      "rrhh@empresa.com")


@pytest.fixture
def candidato_data():
    return {
        "candidato_id":  "uuid-candidato-001",
        "nombre":        "Martina Rodríguez",
        "email":         "martina@example.com",
        "linkedin_url":  "https://linkedin.com/in/martinarodriguez",
        "github_username": "martinard",
        "skills":        ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS", "Kafka"],
        "experiencia": [
            {"empresa": "Mercado Pago", "cargo": "Backend Engineer Sr.", "desde": "2021-03", "hasta": None, "descripcion": "Microservicios de pagos en Python/FastAPI."},
            {"empresa": "Naranja X",    "cargo": "Backend Developer",    "desde": "2019-06", "hasta": "2021-02", "descripcion": "APIs REST para app móvil."},
        ],
        "cv_texto": "Senior backend engineer con 7 años de experiencia...",
    }


@pytest.fixture
def proceso_data():
    return {
        "proceso_id":  "uuid-proceso-001",
        "titulo":      "Senior Backend Engineer – Fintech",
        "jd_texto":    "Buscamos un Senior Backend Engineer con experiencia en Python y sistemas distribuidos.",
    }


@pytest.fixture
def preguntas_data():
    return [
        {"categoria": "técnica",    "pregunta": "¿Cómo implementaron idempotencia en Mercado Pago?", "objetivo": "Evaluar sistemas distribuidos", "nivel": "senior", "tiempo_estimado_min": 8},
        {"categoria": "conductual", "pregunta": "Contame de una decisión difícil bajo presión.",      "objetivo": "Evaluar ownership",            "nivel": "senior", "tiempo_estimado_min": 6},
        {"categoria": "presión",    "pregunta": "Tenés Kafka. ¿Qué es un consumer group?",            "objetivo": "Detectar conocimiento real",    "nivel": "senior", "tiempo_estimado_min": 5},
    ]


@pytest.fixture
def kit_input(candidato_data, proceso_data, preguntas_data):
    return {
        "candidato_id":          candidato_data["candidato_id"],
        "candidato_nombre":      candidato_data["nombre"],
        "proceso_id":            proceso_data["proceso_id"],
        "proceso_titulo":        proceso_data["titulo"],
        "skills":                candidato_data["skills"],
        "experiencia":           candidato_data["experiencia"],
        "preguntas":             preguntas_data,
        "duracion_estimada_min": 30,
    }
