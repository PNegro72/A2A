import base64
import os
from pathlib import Path

import vertexai
from vertexai.generative_models import GenerativeModel, Part

from IPython.display import Markdown, display
from dotenv import load_dotenv

from helpers import authenticate

class PolicyAgent:
    def __init__(self) -> None:
        load_dotenv()
        credentials, project_id = authenticate()

        # Avoid API-key "express mode" selecting gen-lang-client-* projects.
        # Force Vertex AI to use ADC/service-account credentials + explicit project.
        os.environ.pop("GOOGLE_API_KEY", None)
        vertexai.init(
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            credentials=credentials,
        )

        with Path("data/2026AnthemgHIPSBC.pdf").open("rb") as file:
            self.pdf_data = base64.standard_b64encode(file.read()).decode("utf-8")

    def answer_query(self, prompt: str) -> str:

        # 2. Configura el modelo de Google (Gemini) y las instrucciones
        model = GenerativeModel("gemini-2.5-pro", # O "gemini-1.5-pro-002" si el 2.5 aún no está por defecto en tu región
        system_instruction="""You are an expert insurance agent designed to assist with 
        coverage queries. Use the provided documents to answer questions 
        about insurance policies. If the information is not available in 
        the documents, respond with 'I don't know'""")

        # 3. Cargar el PDF (Vertex AI nativo lo hace muy fácil)
        # Nota: pdf_data debe ser los bytes en crudo del PDF (ej: open("archivo.pdf", "rb").read())
        documento_pdf = Part.from_data(mime_type="application/pdf", data=self.pdf_data)

        # 4. Enviar la consulta
        response = model.generate_content(
            [documento_pdf, prompt],
            generation_config={"max_output_tokens": 1024}
        )

        return response.text.replace("$", r"\\$")
