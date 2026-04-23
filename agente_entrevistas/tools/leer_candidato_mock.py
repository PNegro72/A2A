def leer_candidato(candidato_id: str, proceso_id: str) -> dict:
    candidatos = {
        "uuid-test-001": {
            "candidato_id": "uuid-test-001",
            "nombre": "Martina Rodríguez",
            "email": "martinarodriguez@empresa.com",
            "linkedin_url": "https://linkedin.com/in/martinarodriguez",
            "github_username": "martinard",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kafka", "AWS"],
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
            "jd_texto": None,
            "proceso_titulo": "Senior Backend Engineer – Fintech",
        },
        "uuid-test-002": {
            "candidato_id": "uuid-test-002",
            "nombre": "Diego Fernández",
            "email": "diegofernandez@empresa.com",
            "linkedin_url": "https://linkedin.com/in/diegofernandez",
            "github_username": "diegofdev",
            "skills": ["React", "TypeScript", "Node.js", "GraphQL", "AWS", "Docker"],
            "experiencia": [
                {
                    "empresa": "Globant",
                    "cargo": "Frontend Tech Lead",
                    "desde": "2022-01",
                    "hasta": None,
                    "descripcion": "Liderazgo técnico de equipo de 8 personas. Arquitectura frontend para cliente bancario en EEUU.",
                },
                {
                    "empresa": "MercadoLibre",
                    "cargo": "Frontend Developer Sr.",
                    "desde": "2019-04",
                    "hasta": "2021-12",
                    "descripcion": "Desarrollo de componentes React para el flujo de checkout. +50M usuarios.",
                },
            ],
            "cv_texto": "Frontend Tech Lead con 8 años de experiencia en productos de escala.",
            "jd_texto": None,
            "proceso_titulo": "Frontend Tech Lead – E-commerce",
        },
    }

    candidato = candidatos.get(candidato_id)
    if not candidato:
        return {"error": f"Candidato {candidato_id} no encontrado en el mock."}
    return candidato