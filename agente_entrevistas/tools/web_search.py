"""
Tool: web_search
Búsqueda web para verificar información pública del candidato.
Usa Tavily como primario y Serper como fallback.
"""

import os
from typing import Optional

try:
    from tavily import TavilyClient as _TavilyClient
except ImportError:
    _TavilyClient = None

try:
    import requests as _requests
except ImportError:
    _requests = None


def web_search(
    query: str,
    max_results: int = 5,
    include_domains: Optional[list[str]] = None,
) -> dict:
    """
    Busca información pública relevante para la entrevista.
    Útil para verificar empresas del CV, perfil de LinkedIn/GitHub,
    proyectos open source, publicaciones técnicas, etc.

    Args:
        query: Texto de búsqueda.
        max_results: Cantidad máxima de resultados (default 5).
        include_domains: Lista de dominios a priorizar.

    Returns:
        Diccionario con lista de resultados (título, url, snippet) y fuente usada.
    """
    tavily_key = os.environ.get("TAVILY_API_KEY")
    serper_key = os.environ.get("SERPER_API_KEY")

    if tavily_key:
        return _search_tavily(query, max_results, include_domains, tavily_key)
    elif serper_key:
        return _search_serper(query, max_results, serper_key)
    else:
        return {
            "error": "No hay API key configurada (TAVILY_API_KEY o SERPER_API_KEY).",
            "resultados": [],
        }


def _search_tavily(
    query: str,
    max_results: int,
    include_domains: Optional[list[str]],
    api_key: str,
) -> dict:
    try:
        TavilyClient = _TavilyClient
        if TavilyClient is None:
            raise ImportError("tavily not installed")
        client = TavilyClient(api_key=api_key)

        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        if include_domains:
            kwargs["include_domains"] = include_domains

        response = client.search(**kwargs)

        resultados = [
            {
                "titulo":  r.get("title", ""),
                "url":     r.get("url", ""),
                "snippet": r.get("content", "")[:400],
                "score":   r.get("score"),
            }
            for r in response.get("results", [])
        ]

        return {"fuente": "tavily", "resultados": resultados}

    except Exception as e:
        serper_key = os.environ.get("SERPER_API_KEY")
        if serper_key:
            return _search_serper(query, max_results, serper_key)
        return {"error": str(e), "resultados": []}


def _search_serper(query: str, max_results: int, api_key: str) -> dict:
    try:
        requests = _requests
        if requests is None:
            raise ImportError("requests not installed")

        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        resultados = [
            {
                "titulo":  r.get("title", ""),
                "url":     r.get("link", ""),
                "snippet": r.get("snippet", "")[:400],
                "score":   None,
            }
            for r in data.get("organic", [])
        ]

        return {"fuente": "serper", "resultados": resultados}

    except Exception as e:
        return {"error": str(e), "resultados": []}
