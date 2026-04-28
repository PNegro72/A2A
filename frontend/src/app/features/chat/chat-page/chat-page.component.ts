/**
 * ChatPageComponent
 * ----------------------------------------------------------------------------
 * Página principal del chat. Es el "contenedor" que orquesta toda la UI:
 *
 *   - Sidebar de conversaciones (ConversationSidebarComponent)
 *   - Header con título del agente y toggle de tema
 *   - Lista de mensajes (MessageListComponent)
 *   - Input para escribir (ChatInputComponent)
 *
 * Responsabilidades:
 *   - Mantener el estado de UI propio de la página (sidebar abierta, "está
 *     pensando", pasos del agente en curso).
 *   - Coordinar el flujo de envío de un mensaje: agregar mensaje del usuario,
 *     crear placeholder del bot, llamar al OrchestratorService y manejar
 *     el stream de respuesta (pasos intermedios + mensaje final).
 *   - Persistir las conversaciones via ConversationsService (localStorage).
 *
 * NOTA: Este componente NO conoce los detalles de transporte (SSE/polling).
 * Toda esa lógica vive en OrchestratorService.
 */
import {
  Component, OnInit, OnDestroy, signal, computed, inject, ChangeDetectionStrategy,
} from '@angular/core';
import { Subscription } from 'rxjs';
import { ConversationsService } from '../../../core/services/conversations.service';
import { OrchestratorService } from '../../../core/services/orchestrator.service';
import { ThemeService, ThemeMode } from '../../../core/services/theme.service';
import { ConfigService } from '../../../core/services/config.service';
import { LoggerService } from '../../../core/services/logger.service';
import { Message } from '../../../core/models/message.model';
import { AgentStep, FinalMessage, StreamError } from '../../../core/models/agent-step.model';
import { MessageListComponent } from '../message-list/message-list.component';
import { ChatInputComponent } from '../chat-input/chat-input.component';
import { ConversationSidebarComponent } from '../conversation-sidebar/conversation-sidebar.component';

/** Genera un id único. Usa crypto.randomUUID si está disponible, sino fallback simple. */
function generateId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [MessageListComponent, ChatInputComponent, ConversationSidebarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './chat-page.component.html',
  styleUrls: ['./chat-page.component.scss'],
})
export class ChatPageComponent implements OnInit, OnDestroy {
  // --- Servicios inyectados ---
  protected readonly convService = inject(ConversationsService);
  protected readonly orchestrator = inject(OrchestratorService);
  protected readonly themeService = inject(ThemeService);
  protected readonly config = inject(ConfigService);
  private readonly logger = inject(LoggerService);

  // --- Estado de UI ---
  /** True si la sidebar lateral está visible (en mobile arranca cerrada). */
  protected readonly sidebarOpen = signal(false);
  /** True mientras estamos esperando la respuesta del bot (muestra el indicador "Pensando..."). */
  protected readonly isThinking = signal(false);
  /** Pasos intermedios que va emitiendo el orchestrator durante el stream. */
  protected readonly agentSteps = signal<AgentStep[]>([]);

  /** Mensajes de la conversación activa (derivado del ConversationsService). */
  protected readonly currentMessages = computed<Message[]>(() => {
    return this.convService.activeConversation()?.messages ?? [];
  });

  // --- Estado interno del flujo de envío ---
  /** Suscripción activa al stream del orchestrator. La cancelamos al detener o destruir. */
  private streamSub: Subscription | null = null;
  /** Id del mensaje "placeholder" del bot mientras esperamos su respuesta. */
  private pendingBotMessageId: string | null = null;

  ngOnInit(): void {
    // Cargar conversaciones desde localStorage e inicializar tema
    this.convService.load();
    this.themeService.init();

    // En desktop la sidebar arranca abierta; en mobile cerrada
    if (window.innerWidth >= 1024) {
      this.sidebarOpen.set(true);
    }
  }

  ngOnDestroy(): void {
    // Importante: cancelar el stream al destruir el componente para evitar
    // callbacks ejecutándose sobre un componente ya muerto.
    this.streamSub?.unsubscribe();
  }

  /** Cambia la conversación activa. En mobile cierra la sidebar después de seleccionar. */
  protected selectConversation(id: string): void {
    this.convService.setActive(id);
    if (window.innerWidth < 1024) {
      this.sidebarOpen.set(false);
    }
  }

  /** Crea una conversación nueva, la activa, y cierra la sidebar en mobile. */
  protected createNewConversation(): void {
    const conv = this.convService.createConversation();
    this.convService.setActive(conv.id);
    if (window.innerWidth < 1024) {
      this.sidebarOpen.set(false);
    }
  }

  /**
   * Flujo principal cuando el usuario envía un mensaje:
   *   1. Asegurar que existe una conversación activa (si no, crearla).
   *   2. Agregar el mensaje del usuario al historial.
   *   3. Agregar un placeholder del bot con status='sending'.
   *   4. Llamar al orchestrator vía POST /chat para iniciar el request.
   *   5. Cuando responde con el request_id, abrir el stream de pasos.
   */
  protected sendMessage(text: string): void {
    let convId = this.convService.activeConversationId();

    // 1. Si no hay conversación activa, crear una al vuelo
    if (!convId) {
      const conv = this.convService.createConversation();
      convId = conv.id;
    }

    // 2. Mensaje del usuario
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
      status: 'done',
    };
    this.convService.addMessage(convId, userMessage);

    // 3. Placeholder del bot. Lo iremos actualizando a medida que llegan datos.
    const botMessageId = generateId();
    this.pendingBotMessageId = botMessageId;
    const botMessage: Message = {
      id: botMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      status: 'sending',
    };
    this.convService.addMessage(convId, botMessage);

    this.isThinking.set(true);
    this.agentSteps.set([]);

    // 4. POST /chat → recibe { request_id, ... } y abrimos el stream
    this.streamSub = this.orchestrator.sendMessage(convId, text).subscribe({
      next: (initResponse) => {
        this.openStream(initResponse.request_id, convId!, botMessageId);
      },
      error: (err: Error) => {
        this.logger.error('Error iniciando chat', err);
        this.finishWithError(convId!, botMessageId, err.message);
      },
    });
  }

  /**
   * Abre el stream de respuesta (SSE o polling, según config) y procesa
   * cada item que llega:
   *   - 'step'  → agrega el paso al indicador de "Pensando".
   *   - 'final' → completa el placeholder del bot con el contenido final.
   *   - 'error' → marca el placeholder como error.
   */
  private openStream(requestId: string, convId: string, botMessageId: string): void {
    this.streamSub = this.orchestrator.streamResponse(requestId).subscribe({
      next: (item) => {
        if (item.type === 'step') {
          const step = item.data as AgentStep;
          this.agentSteps.update(steps => [...steps, step]);
        } else if (item.type === 'final') {
          const final = item.data as FinalMessage;
          this.convService.updateMessage(convId, botMessageId, {
            content: final.content,
            status: 'done',
            timestamp: new Date(),
          });
          this.finishThinking();
        } else if (item.type === 'error') {
          const err = item.data as StreamError;
          this.finishWithError(convId, botMessageId, err.message);
        }
      },
      error: (err: Error) => {
        this.logger.error('Error en stream', err);
        this.finishWithError(convId, botMessageId, err.message);
      },
      complete: () => {
        this.finishThinking();
      },
    });
  }

  /**
   * Cancela manualmente la respuesta en curso. Marca el placeholder del bot
   * como 'cancelled' y limpia el estado de "Pensando".
   */
  protected stopResponse(): void {
    this.streamSub?.unsubscribe();
    this.streamSub = null;

    const convId = this.convService.activeConversationId();
    if (convId && this.pendingBotMessageId) {
      this.convService.updateMessage(convId, this.pendingBotMessageId, {
        status: 'cancelled',
        content: '',
      });
    }
    this.finishThinking();
  }

  /**
   * Reintenta la última pregunta del usuario cuando el bot devolvió error.
   * Reutiliza el mismo mensaje del bot (limpiándolo) en lugar de crear uno nuevo.
   */
  protected retry(): void {
    const conv = this.convService.activeConversation();
    if (!conv) return;

    // Buscamos el último mensaje del usuario y el último del bot
    const messages = conv.messages;
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      const lastBotMsg = [...messages].reverse().find(m => m.role === 'assistant');
      if (lastBotMsg) {
        // Reseteamos el mensaje del bot a 'sending' para volver a intentar
        this.convService.updateMessage(conv.id, lastBotMsg.id, {
          status: 'sending',
          content: '',
          errorMessage: undefined,
        });
        this.pendingBotMessageId = lastBotMsg.id;
        this.isThinking.set(true);
        this.agentSteps.set([]);

        this.streamSub = this.orchestrator.sendMessage(conv.id, lastUserMsg.content).subscribe({
          next: (initResponse) => {
            this.openStream(initResponse.request_id, conv.id, lastBotMsg.id);
          },
          error: (err: Error) => {
            this.finishWithError(conv.id, lastBotMsg.id, err.message);
          },
        });
      }
    }
  }

  /** Limpia el estado de "Pensando" cuando termina (con éxito o error) la respuesta. */
  private finishThinking(): void {
    this.isThinking.set(false);
    this.agentSteps.set([]);
    this.pendingBotMessageId = null;
  }

  /** Marca el placeholder del bot como error y termina el flujo. */
  private finishWithError(convId: string, botMessageId: string, errorMessage: string): void {
    this.convService.updateMessage(convId, botMessageId, {
      status: 'error',
      errorMessage,
      content: '',
    });
    this.finishThinking();
  }

  /** Texto del tooltip del botón de tema según el modo activo. */
  protected themeLabel(): string {
    const mode: ThemeMode = this.themeService.mode();
    return mode === 'light' ? 'Tema claro (click para oscuro)'
      : mode === 'dark' ? 'Tema oscuro (click para automático)'
      : 'Tema automático (click para claro)';
  }

  /** Avanza al siguiente modo de tema (light → dark → system → light). */
  protected cycleTheme(): void {
    this.themeService.toggleMode();
  }

  /** Abre/cierra la sidebar (usado por el botón hamburguesa en mobile). */
  protected toggleSidebar(): void {
    this.sidebarOpen.update(v => !v);
  }
}
