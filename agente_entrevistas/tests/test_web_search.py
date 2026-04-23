import pytest
from unittest.mock import patch, MagicMock
import agente_entrevistas.tools.web_search as _ws_mod


RESULTADOS_TAVILY = {"results": [{"title": "Martina | LinkedIn", "url": "https://linkedin.com/in/martina", "content": "Senior Backend Engineer...", "score": 0.92}]}
RESULTADOS_SERPER = {"organic": [{"title": "Martina | LinkedIn", "link": "https://linkedin.com/in/martina", "snippet": "Senior Backend Engineer..."}]}


class TestWebSearch:

    def test_usa_tavily_cuando_hay_key(self):
        with patch("os.environ.get") as mock_env, \
             patch.object(_ws_mod, "_search_tavily") as mock_tavily:
            mock_env.side_effect = lambda k, d=None: {"TAVILY_API_KEY": "t-key", "SERPER_API_KEY": None}.get(k, d)
            mock_tavily.return_value = {"fuente": "tavily", "resultados": []}
            from agente_entrevistas.tools.web_search import web_search
            web_search("Martina LinkedIn")
        mock_tavily.assert_called_once()

    def test_usa_serper_cuando_no_hay_tavily(self):
        with patch("os.environ.get") as mock_env, \
             patch.object(_ws_mod, "_search_serper") as mock_serper:
            mock_env.side_effect = lambda k, d=None: {"TAVILY_API_KEY": None, "SERPER_API_KEY": "s-key"}.get(k, d)
            mock_serper.return_value = {"fuente": "serper", "resultados": []}
            from agente_entrevistas.tools.web_search import web_search
            web_search("Martina LinkedIn")
        mock_serper.assert_called_once()

    def test_sin_ninguna_key_retorna_error(self):
        with patch("os.environ.get", return_value=None):
            from agente_entrevistas.tools.web_search import web_search
            result = web_search("test query")
        assert "error" in result
        assert result["resultados"] == []

    def test_estructura_resultado_tavily(self):
        mock_instance = MagicMock()
        mock_instance.search.return_value = RESULTADOS_TAVILY
        mock_class = MagicMock(return_value=mock_instance)
        with patch.object(_ws_mod, "_TavilyClient", mock_class):
            from agente_entrevistas.tools.web_search import _search_tavily
            result = _search_tavily("test", 5, None, "fake-key")
        assert result["fuente"] == "tavily"
        assert len(result["resultados"]) == 1
        assert result["resultados"][0]["url"] == "https://linkedin.com/in/martina"

    def test_estructura_resultado_serper(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = RESULTADOS_SERPER
        mock_resp.raise_for_status.return_value = None
        with patch.object(_ws_mod._requests, "post", return_value=mock_resp):
            from agente_entrevistas.tools.web_search import _search_serper
            result = _search_serper("test", 5, "fake-key")
        assert result["fuente"] == "serper"
        assert result["resultados"][0]["url"] == "https://linkedin.com/in/martina"

    def test_tavily_falla_hace_fallback_a_serper(self):
        with patch.object(_ws_mod, "_TavilyClient", side_effect=Exception("timeout")), \
             patch.object(_ws_mod, "_search_serper") as mock_serper:
            mock_serper.return_value = {"fuente": "serper", "resultados": []}
            with patch("os.environ.get", return_value="s-key"):
                from agente_entrevistas.tools.web_search import _search_tavily
                result = _search_tavily("test", 3, None, "t-key")
        assert result["fuente"] == "serper"

    def test_snippet_truncado_a_400_chars(self):
        resultado_largo = {"results": [{"title": "T", "url": "https://x.com", "content": "x" * 1000, "score": 0.5}]}
        mock_instance = MagicMock()
        mock_instance.search.return_value = resultado_largo
        mock_class = MagicMock(return_value=mock_instance)
        with patch.object(_ws_mod, "_TavilyClient", mock_class):
            from agente_entrevistas.tools.web_search import _search_tavily
            result = _search_tavily("test", 1, None, "fake-key")
        assert len(result["resultados"][0]["snippet"]) <= 400

    def test_include_domains_se_pasa_a_tavily(self):
        mock_instance = MagicMock()
        mock_instance.search.return_value = {"results": []}
        mock_class = MagicMock(return_value=mock_instance)
        with patch.object(_ws_mod, "_TavilyClient", mock_class):
            from agente_entrevistas.tools.web_search import _search_tavily
            _search_tavily("test", 3, ["linkedin.com", "github.com"], "fake-key")
        assert mock_instance.search.call_args[1].get("include_domains") == ["linkedin.com", "github.com"]
