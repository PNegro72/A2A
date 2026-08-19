"""
Script standalone para generar el token.json de OAuth2 la primera vez.

Uso (desde la carpeta agente_scheduling/, con el venv activado):

    python setup_oauth.py

Requisitos previos:
  1. Tener un proyecto en Google Cloud Console con la Google Calendar API y la
     Gmail API habilitadas.
  2. Haber creado credenciales OAuth2 de tipo "Desktop app" y descargado el JSON
     como `credentials.json` en esta misma carpeta (o la ruta indicada por
     GOOGLE_CREDENTIALS_FILE).

Qué hace:
  - Carga credentials.json.
  - Abre el browser para que autorices con la cuenta de Gmail del organizador
    (la cuenta cuyo calendario se usará para crear los eventos y desde la que
    se envían los emails de la acción send_email).
  - Guarda el token resultante en token.json (o GOOGLE_TOKEN_FILE).

Una vez generado token.json, el servidor (server.py) lo reutiliza y lo refresca
automáticamente; no hace falta volver a correr este script salvo que el token se
revoque o se cambien los scopes (usa los mismos SCOPES que calendar_service.py,
para que nunca queden desincronizados).
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

from google_auth_oauthlib.flow import InstalledAppFlow

from calendar_service import SCOPES


def main() -> None:
    credentials_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    token_file = os.environ.get("GOOGLE_TOKEN_FILE", "token.json")

    if not os.path.exists(credentials_file):
        raise SystemExit(
            f"No se encontró '{credentials_file}'. Descargá las credenciales OAuth2 "
            "(tipo 'Desktop app') desde Google Cloud Console y colocá el archivo aquí."
        )

    print("Abriendo el browser para autorizar acceso a Google Calendar y Gmail...")
    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_file, "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    print(f"[OK] Token guardado en '{token_file}'. Ya podes correr: python server.py")


if __name__ == "__main__":
    main()
