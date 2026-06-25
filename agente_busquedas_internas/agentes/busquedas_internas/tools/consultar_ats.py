"""
Herramienta: consultar_ats

Busca candidatos internos relevantes para una posición.

Fuente de datos: el servidor MCP de RAGaaS (carpeta ``MCP/``), que expone una
base de conocimiento RAG sobre Qdrant. Esta tool CONSUME la tool ``search`` del
MCP (búsqueda semántica) vía ``ragaas_client.buscar_chunks`` y reconstruye, a
partir de los chunks devueltos, un candidato por documento (CV) indexado.

Los datos provienen del servidor MCP de RAGaaS (búsqueda semántica sobre Qdrant).
El prompt del agente, los schemas y el ranking del LLM no cambian.

Mapeo MCP → candidato:
    - Cada CV está indexado en Qdrant como un documento (``source_file``)
      partido en uno o más chunks.
    - Agrupamos los chunks por ``source_file``, concatenamos su texto en orden
      (``chunk_index``) para reconstruir ``texto_cv``, y tomamos el mejor score
      de chunk como ``score_embedding`` del candidato.
"""
import logging
from collections import OrderedDict
from pathlib import Path

from agentes.busquedas_internas.ragaas_client import buscar_chunks
from agentes.config.settings import get_settings
from schemas.busqueda_response import Busqueda_response
from schemas.cvs_data import Cvs_data
from schemas.JobDescriptionEstructurada import JobDescriptionEstructurada

logger = logging.getLogger(__name__)


def _agrupar_chunks_por_cv(chunks: list[dict]) -> list[Cvs_data]:
    """Agrupa los chunks del MCP en un candidato por documento (``source_file``).

    Reconstruye el texto del CV concatenando sus chunks en orden y usa el mejor
    score de chunk como score del candidato. Devuelve la lista ordenada de mayor
    a menor score.
    """
    por_archivo: "OrderedDict[str, list[dict]]" = OrderedDict()
    for ch in chunks:
        source = ch.get("source_file") or "—"
        por_archivo.setdefault(source, []).append(ch)

    candidatos: list[Cvs_data] = []
    for source, group in por_archivo.items():
        ordenados = sorted(group, key=lambda c: c.get("chunk_index", 0))
        texto = "\n\n".join(
            (c.get("text") or "").strip() for c in ordenados if c.get("text")
        )
        mejor_score = max((float(c.get("score", 0.0)) for c in group), default=0.0)
        mejor_score = max(0.0, min(1.0, mejor_score))  # clamp defensivo a [0,1]
        nombre = Path(source).stem or source
        candidatos.append(
            Cvs_data(
                id=nombre,
                nombre=nombre,
                texto_cv=texto,
                score_embedding=round(mejor_score, 4),
            )
        )

    candidatos.sort(key=lambda c: c.score_embedding, reverse=True)
    return candidatos


async def Consultar_ats(job_description: JobDescriptionEstructurada) -> dict:
    """
    Busca candidatos internos relevantes para una posición.

    Consulta el ATS (base RAG sobre Qdrant, vía el servidor MCP de RAGaaS) y
    devuelve los CVs más similares a la JD por búsqueda semántica. Cada candidato
    incluye el texto reconstruido de su CV para que el LLM pueda extraer los
    campos estructurados (nombre, skills, experiencia, etc.) y rankearlo.

    Args:
        job_description: Job Description estructurada con role_title, role_description,
                         management_level y skills.

    Returns:
        dict con estructura:
            {
                "exito": bool,
                "candidatos": list[dict],
                "total": int,
                "mensaje": str
            }

        Cada elemento de "candidatos":
            {
                "id": str,               # nombre del documento sin extensión
                "nombre": str,           # ídem (legibilidad para el LLM)
                "texto_cv": str,         # texto del CV reconstruido desde los chunks
                "score_embedding": float # mejor score de similitud con la JD (0.0–1.0)
            }
    """
    settings = get_settings()

    jd_texto = " ".join([
        job_description.role_title,
        job_description.role_description,
        job_description.management_level,
        " ".join(job_description.skills),
    ])

    # Si la JD trae un número explícito, lo usamos (clampeado al rango [1, MAX_TOP_N]).
    # Si no, caemos al default seguro para el modelo configurado.
    requested = job_description.cantidad_candidatos
    if requested is None or requested <= 0:
        top_n = settings.DEFAULT_TOP_N
    else:
        top_n = min(requested, settings.MAX_TOP_N)

    # Pedimos más chunks que candidatos: cada CV puede estar partido en varios.
    # El MCP topea top_k en 50.
    top_k = min(50, max(top_n, top_n * settings.RAGAAS_CHUNKS_PER_CANDIDATE))

    logger.info(
        "Consultar_ats | cantidad_candidatos=%s -> top_n=%s, top_k(chunks)=%s, collection=%s",
        requested, top_n, top_k, settings.RAGAAS_COLLECTION,
    )

    try:
        chunks = await buscar_chunks(
            mcp_url=settings.RAGAAS_MCP_URL,
            query=jd_texto,
            top_k=top_k,
            min_score=settings.RAGAAS_MIN_SCORE,
            collection=settings.RAGAAS_COLLECTION,
        )
    except Exception as exc:  # noqa: BLE001 — queremos degradar, no romper el agente
        logger.exception("Consultar_ats | falló la consulta al MCP de RAGaaS")
        response = Busqueda_response(
            exito=False,
            candidatos=[],
            total=0,
            mensaje=(
                f"No se pudo consultar el MCP de RAGaaS en {settings.RAGAAS_MCP_URL}. "
                f"¿Están corriendo el servidor MCP y el backend RAGaaS (:8000)? "
                f"Detalle: {exc}"
            ),
        )
        return response.model_dump(exclude={"candidatos": {"__all__": {"embedding"}}})

    candidatos = _agrupar_chunks_por_cv(chunks)[:top_n]

    # Truncar texto_cv para acotar el contexto que recibe el LLM downstream.
    for cv in candidatos:
        if cv.texto_cv and len(cv.texto_cv) > settings.MAX_CHARS_POR_CV:
            cv.texto_cv = cv.texto_cv[:settings.MAX_CHARS_POR_CV] + "\n…[CV truncado]"

    total_chars = sum(len(c.texto_cv or "") for c in candidatos)
    logger.info(
        "Consultar_ats | devolviendo %s candidatos, %s chars totales (~%s tokens)",
        len(candidatos), total_chars, total_chars // 4,
    )

    response = Busqueda_response(
        exito=bool(candidatos),
        candidatos=candidatos,
        total=len(candidatos),
        mensaje=(
            f"Se encontraron {len(candidatos)} candidatos en la colección "
            f"'{settings.RAGAAS_COLLECTION}'."
            if candidatos
            else f"No se encontraron candidatos en la colección '{settings.RAGAAS_COLLECTION}'."
        ),
    )
    return response.model_dump(exclude={"candidatos": {"__all__": {"embedding"}}})
