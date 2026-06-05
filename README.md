

## Observabilidad

Los tres componentes principales (`agente_orchestrator`, `agente_busquedas_internas`, `agente_job_description`) envían trazas a **Langfuse** via OpenTelemetry + OpenInference ADK instrumentation. Esto permite ver tokens consumidos, costo y latencia por agente en tiempo real.

### Conseguir las claves

1. Crear cuenta en [Langfuse Cloud](https://us.cloud.langfuse.com) (US) o [cloud.langfuse.com](https://cloud.langfuse.com) (EU).
2. Ir a **Settings → API Keys** y crear un par de claves de proyecto.
3. Copiar `LANGFUSE_PUBLIC_KEY` (`pk-lf-...`) y `LANGFUSE_SECRET_KEY` (`sk-lf-...`).

### Configurar en cada componente

En el `.env` de cada agente (usar `.env.example` como base):

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com   # o https://cloud.langfuse.com para EU
```

Si las variables están ausentes, el agente arranca normalmente sin observabilidad (advertencia en logs).
Si las variables están presentes pero son inválidas, el arranque falla con error explícito.

### Ver los datos

Una vez que haya tráfico, los dashboards relevantes en Langfuse son:

- **Traces** → cada request end-to-end, con los spans de ADK (LLM calls, tool calls, agentes intermedios)
- **Dashboard → Cost** → tokens y costo por modelo, por agente (`service.name`), por día
- **Users** → filtrar por `recruiting_orchestrator`, `busquedas_internas`, `job_description`

## Desarrollo

- Los archivos sensibles y entornos locales estan excluidos por `.gitignore`.
- Los notebooks se usan como entorno de pruebas y orquestacion.
- El proyecto mezcla integraciones A2A, MCP, LangChain y Vertex AI, por lo que conviene validar credenciales antes de probar cada agente.
