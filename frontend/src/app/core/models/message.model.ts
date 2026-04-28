/**
 * Modelo de un mensaje individual dentro de una conversación.
 *
 * Cada mensaje del chat — sea del usuario o del bot — se representa
 * con esta interfaz. Los mensajes del bot empiezan con status='sending'
 * (mientras esperamos la respuesta del orchestrator) y luego se actualizan
 * a 'done', 'error' o 'cancelled' según el resultado.
 */

/** Quién emitió el mensaje. */
export type MessageRole = 'user' | 'assistant';

/**
 * Estado del mensaje:
 *   - 'sending':   placeholder del bot mientras esperamos respuesta.
 *   - 'done':      mensaje final, mostrado normalmente.
 *   - 'error':     hubo un error procesando — se muestra errorMessage + botón Reintentar.
 *   - 'cancelled': el usuario presionó "detener" antes de recibir respuesta.
 */
export type MessageStatus = 'sending' | 'done' | 'error' | 'cancelled';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  status: MessageStatus;
  /** Texto del error a mostrar (sólo cuando status === 'error'). */
  errorMessage?: string;
  /** Id del request original — útil para debug o para reintentar. */
  requestId?: string;
}
