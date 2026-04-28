/**
 * Tipos relacionados al stream de respuesta del orchestrator.
 *
 * Cuando el usuario manda un mensaje, el orchestrator coordina varios
 * "agentes" internos (búsqueda interna, JD, entrevistas, etc.) y va
 * emitiendo eventos en tiempo real. La UI los recibe como una secuencia
 * de StreamItems.
 */

/** Estado en el que está cada paso del agente mientras se ejecuta. */
export type StepStatus = 'running' | 'done' | 'error';

/**
 * Un paso intermedio que reporta uno de los agentes (ej: "Buscando candidatos
 * en ATS...", "Generando preguntas de entrevista..."). Se muestra en el
 * ThinkingIndicatorComponent.
 */
export interface AgentStep {
  agent: string;        // nombre del agente que reporta (ej: 'busquedas_internas')
  status: StepStatus;
  message: string;      // texto a mostrar al usuario
  timestamp: Date;
}

/** Respuesta de POST /chat: contiene los datos para conectarse al stream. */
export interface StreamInitResponse {
  conversation_id: string;
  request_id: string;
  stream_url: string;
}

/** Mensaje final del bot. Llega al cerrar el stream con éxito. */
export interface FinalMessage {
  role: 'assistant';
  content: string;
}

/** Error reportado por el stream o por el endpoint de status. */
export interface StreamError {
  code: string;
  message: string;
}

/** Tipo discriminado para los items emitidos por el Observable del stream. */
export type StreamItemType = 'step' | 'final' | 'error';

/**
 * Unidad común que emite el OrchestratorService, sea SSE o polling.
 * El consumidor sólo tiene que mirar `type` y castear `data` en consecuencia.
 */
export interface StreamItem {
  type: StreamItemType;
  data: AgentStep | FinalMessage | StreamError;
}
