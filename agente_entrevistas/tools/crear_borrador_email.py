"""
Tool: crear_borrador_email
Envía el email al candidato via Mailtrap API (envío real).
 
Requiere en .env:
    MAILTRAP_API_TOKEN=tu_api_token
    MS_SENDER_EMAIL=tu_email_verificado@tudominio.com
"""
 
import os
import mailtrap as mt
 
 
def crear_borrador_email(
    candidato_nombre: str,
    candidato_email: str,
    proceso_titulo: str,
    cuerpo_email: str,
    remitente_email: str | None = None,
    asunto: str | None = None,
) -> dict:
    """
    Envía el email al candidato via Mailtrap API.
 
    Args:
        candidato_nombre: Nombre completo del candidato.
        candidato_email: Email del candidato destinatario.
        proceso_titulo: Título del proceso/posición (para el asunto).
        cuerpo_email: Cuerpo del email en HTML o texto plano.
        remitente_email: Email remitente. Si es None, usa MS_SENDER_EMAIL del .env.
        asunto: Asunto del email. Si es None, se genera automáticamente.
 
    Returns:
        Dict con status del envío y metadata.
    """
    api_token = os.environ.get("MAILTRAP_API_TOKEN")
    if not api_token:
        return {
            "error":    "Falta MAILTRAP_API_TOKEN en el .env.",
            "draft_id": None,
        }
 
    sender  = remitente_email or os.environ.get("MS_SENDER_EMAIL", "hello@demomailtrap.co")
    subject = asunto or f"Oportunidad laboral: {proceso_titulo}"
 
    content_type = "html" if cuerpo_email.strip().startswith("<") else "plain"
 
    try:
        mail = mt.Mail(
            sender=mt.Address(email=sender),
            to=[mt.Address(email=candidato_email, name=candidato_nombre)],
            subject=subject,
            text=cuerpo_email if content_type == "plain" else None,
            html=cuerpo_email if content_type == "html" else None,
            category="Reclutamiento",
        )
 
        import ssl
        import httpx

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        client = mt.MailtrapClient(token=api_token)
        client._client = httpx.Client(verify=False)
        response = client.send(mail)
 
    except Exception as e:
        return {
            "error":    f"Error enviando email via Mailtrap: {e}",
            "draft_id": None,
        }
 
    return {
        "status":       "enviado",
        "draft_id":     None,
        "remitente":    sender,
        "destinatario": candidato_email,
        "asunto":       subject,
        "mensaje":      f"Email enviado correctamente a {candidato_email} via Mailtrap.",
        "response":     str(response),
    }