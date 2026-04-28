/**
 * Modelos de conversación.
 *
 * Hay 2 representaciones:
 *   - Conversation / Message:               la usada en runtime (con `Date`).
 *   - SerializedConversation / SerializedMessage: la usada al persistir
 *     en localStorage (fechas como ISO strings, porque JSON no soporta Date).
 *
 * El ConversationsService convierte de una a otra al guardar/cargar.
 */
import { Message } from './message.model';

/** Conversación tal como se usa en la UI (con instancias de Date). */
export interface Conversation {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
}

/** Wrapper persistido en localStorage: incluye versión de schema para migrar a futuro. */
export interface ConversationsStorage {
  version: 1;
  conversations: SerializedConversation[];
}

/** Versión serializada de una conversación (fechas como strings ISO). */
export interface SerializedConversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: SerializedMessage[];
}

/** Versión serializada de un mensaje (timestamp como string ISO). */
export interface SerializedMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  status: 'sending' | 'done' | 'error' | 'cancelled';
  errorMessage?: string;
  requestId?: string;
}
