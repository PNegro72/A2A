/**
 * ConversationsService
 * ----------------------------------------------------------------------------
 * Gestiona la lista de conversaciones del usuario y las persiste en
 * localStorage (clave 'sape-conversations').
 *
 * Es la única fuente de verdad sobre las conversaciones: cualquier cambio
 * (crear, agregar mensaje, renombrar, borrar) actualiza los signals y
 * dispara save() automáticamente.
 *
 * Estado público:
 *   - conversations:        signal con la lista completa.
 *   - activeConversationId: signal con el id de la conversación activa.
 *   - activeConversation:   computed que devuelve la conversación activa o null.
 *
 * Detalles de persistencia:
 *   - Las fechas se serializan como ISO strings (JSON.stringify pierde
 *     instancias de Date), y se rehidratan a Date al cargar.
 *   - Se guarda un campo `version` en el JSON para poder migrar el schema
 *     en el futuro si cambia. Si la versión guardada no coincide,
 *     se ignora el storage (no se borra, por las dudas).
 */
import { Injectable, signal, computed } from '@angular/core';
import { LoggerService } from './logger.service';
import { Conversation, ConversationsStorage, SerializedConversation } from '../models/conversation.model';
import { Message } from '../models/message.model';

/** Clave usada para persistir el storage en localStorage. */
const STORAGE_KEY = 'sape-conversations';
/** Versión del schema persistido. Subir si cambia la forma de los datos. */
const SCHEMA_VERSION = 1;

/** Genera un id único. Usa crypto.randomUUID si está disponible, sino fallback simple. */
function generateId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

/** Convierte la versión serializada (con fechas como string) a la del runtime (Date). */
function deserializeConversation(s: SerializedConversation): Conversation {
  return {
    ...s,
    createdAt: new Date(s.createdAt),
    updatedAt: new Date(s.updatedAt),
    messages: s.messages.map(m => ({
      ...m,
      timestamp: new Date(m.timestamp),
    })),
  };
}

/** Convierte la conversación de runtime (Date) a su forma serializable (string). */
function serializeConversation(c: Conversation): SerializedConversation {
  return {
    ...c,
    createdAt: c.createdAt.toISOString(),
    updatedAt: c.updatedAt.toISOString(),
    messages: c.messages.map(m => ({
      ...m,
      timestamp: m.timestamp.toISOString(),
    })),
  };
}

@Injectable({ providedIn: 'root' })
export class ConversationsService {
  private readonly logger = new LoggerService();

  readonly conversations = signal<Conversation[]>([]);
  readonly activeConversationId = signal<string | null>(null);

  readonly activeConversation = computed(() => {
    const id = this.activeConversationId();
    return this.conversations().find(c => c.id === id) ?? null;
  });

  /**
   * Carga las conversaciones desde localStorage al iniciar la app.
   * Se llama desde ChatPageComponent.ngOnInit.
   */
  load(): void {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const storage: ConversationsStorage = JSON.parse(raw);
      if (storage.version !== SCHEMA_VERSION) {
        this.logger.warn('Versión de schema de conversaciones desconocida, ignorando', storage.version);
        return;
      }

      const convs = storage.conversations.map(deserializeConversation);
      this.conversations.set(convs);

      // Activar la primera conversación si hay alguna
      if (convs.length > 0) {
        this.activeConversationId.set(convs[0].id);
      }
    } catch (e) {
      this.logger.error('Error leyendo conversaciones de localStorage', e);
    }
  }

  /** Persiste el estado actual de las conversaciones en localStorage. */
  private save(): void {
    try {
      const storage: ConversationsStorage = {
        version: 1,
        conversations: this.conversations().map(serializeConversation),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(storage));
    } catch (e) {
      this.logger.error('Error guardando conversaciones en localStorage', e);
    }
  }

  /** Crea una conversación nueva, la agrega al inicio de la lista y la activa. */
  createConversation(): Conversation {
    const conv: Conversation = {
      id: generateId(),
      title: 'Nueva conversación',
      createdAt: new Date(),
      updatedAt: new Date(),
      messages: [],
    };
    this.conversations.update(convs => [conv, ...convs]);
    this.activeConversationId.set(conv.id);
    this.save();
    return conv;
  }

  /** Cambia la conversación activa por id. */
  setActive(id: string): void {
    this.activeConversationId.set(id);
  }

  /**
   * Agrega un mensaje al final de una conversación.
   *
   * Side-effect: si es el PRIMER mensaje del usuario y la conversación todavía
   * tiene el título por defecto ("Nueva conversación"), se auto-titula con
   * los primeros 40 caracteres del mensaje (más "..." si fue truncado).
   */
  addMessage(conversationId: string, message: Message): void {
    this.conversations.update(convs =>
      convs.map(c => {
        if (c.id !== conversationId) return c;

        // Auto-title: primeros 40 chars del primer mensaje del usuario
        let title = c.title;
        if (c.messages.length === 0 && message.role === 'user' && title === 'Nueva conversación') {
          title = message.content.slice(0, 40) + (message.content.length > 40 ? '...' : '');
        }

        return {
          ...c,
          title,
          updatedAt: new Date(),
          messages: [...c.messages, message],
        };
      })
    );
    this.save();
  }

  /**
   * Actualiza parcialmente un mensaje existente. Se usa, por ejemplo, para:
   *   - Llenar el contenido del placeholder del bot cuando llega la respuesta.
   *   - Marcar un mensaje como 'error' o 'cancelled'.
   */
  updateMessage(conversationId: string, messageId: string, updates: Partial<Message>): void {
    this.conversations.update(convs =>
      convs.map(c => {
        if (c.id !== conversationId) return c;
        return {
          ...c,
          updatedAt: new Date(),
          messages: c.messages.map(m => m.id === messageId ? { ...m, ...updates } : m),
        };
      })
    );
    this.save();
  }

  /** Cambia el título de una conversación. */
  renameConversation(id: string, title: string): void {
    this.conversations.update(convs =>
      convs.map(c => c.id === id ? { ...c, title, updatedAt: new Date() } : c)
    );
    this.save();
  }

  /**
   * Elimina una conversación. Si la borrada era la activa, activa
   * la primera de las que quedan (o null si no queda ninguna).
   */
  deleteConversation(id: string): void {
    this.conversations.update(convs => convs.filter(c => c.id !== id));

    // Si borramos la activa, activar la primera que quede
    if (this.activeConversationId() === id) {
      const remaining = this.conversations();
      this.activeConversationId.set(remaining.length > 0 ? remaining[0].id : null);
    }
    this.save();
  }
}
