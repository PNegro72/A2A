/**
 * ChatPageComponent
 * ----------------------------------------------------------------------------
 * Página principal del chat. Maneja mensajes de texto y mensajes con archivos
 * adjuntos (CV en PDF/Word para análisis).
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
import { ChatInputComponent, MessageWithFile } from '../chat-input/chat-input.component';
import { ConversationSidebarComponent } from '../conversation-sidebar/conversation-sidebar.component';

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
  protected readonly convService  = inject(ConversationsService);
  protected readonly orchestrator = inject(OrchestratorService);
  protected readonly themeService = inject(ThemeService);
  protected readonly config       = inject(ConfigService);
  private readonly logger         = inject(LoggerService);

  protected readonly sidebarOpen  = signal(false);
  protected readonly isThinking   = signal(false);
  protected readonly agentSteps   = signal<AgentStep[]>([]);

  protected readonly currentMessages = computed<Message[]>(() => {
    return this.convService.activeConversation()?.messages ?? [];
  });

  private streamSub: Subscription | null = null;
  private pendingBotMessageId: string | null = null;

  ngOnInit(): void {
    this.convService.load();
    this.themeService.init();
    if (window.innerWidth >= 1024) {
      this.sidebarOpen.set(true);
    }
  }

  ngOnDestroy(): void {
    this.streamSub?.unsubscribe();
  }

  protected selectConversation(id: string): void {
    this.convService.setActive(id);
    if (window.innerWidth < 1024) {
      this.sidebarOpen.set(false);
    }
  }

  protected createNewConversation(): void {
    const conv = this.convService.createConversation();
    this.convService.setActive(conv.id);
    if (window.innerWidth < 1024) {
      this.sidebarOpen.set(false);
    }
  }

  protected sendMessage(text: string): void {
    let convId = this.convService.activeConversationId();
    if (!convId) {
      const conv = this.convService.createConversation();
      convId = conv.id;
    }

    const userMessage: Message = {
      id: generateId(), role: 'user', content: text,
      timestamp: new Date(), status: 'done',
    };
    this.convService.addMessage(convId, userMessage);

    const botMessageId = generateId();
    this.pendingBotMessageId = botMessageId;
    this.convService.addMessage(convId, {
      id: botMessageId, role: 'assistant', content: '',
      timestamp: new Date(), status: 'sending',
    });

    this.isThinking.set(true);
    this.agentSteps.set([]);

    this.streamSub = this.orchestrator.sendMessage(convId, text).subscribe({
      next: (initResponse) => this.openStream(initResponse.request_id, convId!, botMessageId),
      error: (err: Error) => {
        this.logger.error('Error iniciando chat', err);
        this.finishWithError(convId!, botMessageId, err.message);
      },
    });
  }

  /**
   * Envía un mensaje con archivo adjunto (CV en PDF/Word).
   * El archivo se convierte a base64 y se incluye en el payload del orchestrator.
   */
  protected sendMessageWithFile(payload: MessageWithFile): void {
    let convId = this.convService.activeConversationId();
    if (!convId) {
      const conv = this.convService.createConversation();
      convId = conv.id;
    }

    // Mostrar el mensaje del usuario con el nombre del archivo adjunto
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: `${payload.text}\n📎 ${payload.fileName}`,
      timestamp: new Date(),
      status: 'done',
    };
    this.convService.addMessage(convId, userMessage);

    const botMessageId = generateId();
    this.pendingBotMessageId = botMessageId;
    this.convService.addMessage(convId, {
      id: botMessageId, role: 'assistant', content: '',
      timestamp: new Date(), status: 'sending',
    });

    this.isThinking.set(true);
    this.agentSteps.set([]);

    this.streamSub = this.orchestrator.sendMessageWithFile(convId, payload).subscribe({
      next: (initResponse) => this.openStream(initResponse.request_id, convId!, botMessageId),
      error: (err: Error) => {
        this.logger.error('Error iniciando chat con archivo', err);
        this.finishWithError(convId!, botMessageId, err.message);
      },
    });
  }

  private openStream(requestId: string, convId: string, botMessageId: string): void {
    this.streamSub = this.orchestrator.streamResponse(requestId).subscribe({
      next: (item) => {
        if (item.type === 'step') {
          this.agentSteps.update(steps => [...steps, item.data as AgentStep]);
        } else if (item.type === 'final') {
          const final = item.data as FinalMessage;
          this.convService.updateMessage(convId, botMessageId, {
            content: final.content, status: 'done', timestamp: new Date(),
          });
          this.finishThinking();
        } else if (item.type === 'error') {
          this.finishWithError(convId, botMessageId, (item.data as StreamError).message);
        }
      },
      error: (err: Error) => {
        this.logger.error('Error en stream', err);
        this.finishWithError(convId, botMessageId, err.message);
      },
      complete: () => this.finishThinking(),
    });
  }

  protected stopResponse(): void {
    this.streamSub?.unsubscribe();
    this.streamSub = null;
    const convId = this.convService.activeConversationId();
    if (convId && this.pendingBotMessageId) {
      this.convService.updateMessage(convId, this.pendingBotMessageId, {
        status: 'cancelled', content: '',
      });
    }
    this.finishThinking();
  }

  protected retry(): void {
    const conv = this.convService.activeConversation();
    if (!conv) return;
    const messages = conv.messages;
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      const lastBotMsg = [...messages].reverse().find(m => m.role === 'assistant');
      if (lastBotMsg) {
        this.convService.updateMessage(conv.id, lastBotMsg.id, {
          status: 'sending', content: '', errorMessage: undefined,
        });
        this.pendingBotMessageId = lastBotMsg.id;
        this.isThinking.set(true);
        this.agentSteps.set([]);
        this.streamSub = this.orchestrator.sendMessage(conv.id, lastUserMsg.content).subscribe({
          next: (initResponse) => this.openStream(initResponse.request_id, conv.id, lastBotMsg.id),
          error: (err: Error) => this.finishWithError(conv.id, lastBotMsg.id, err.message),
        });
      }
    }
  }

  private finishThinking(): void {
    this.isThinking.set(false);
    this.agentSteps.set([]);
    this.pendingBotMessageId = null;
  }

  private finishWithError(convId: string, botMessageId: string, errorMessage: string): void {
    this.convService.updateMessage(convId, botMessageId, {
      status: 'error', errorMessage, content: '',
    });
    this.finishThinking();
  }

  protected themeLabel(): string {
    const mode: ThemeMode = this.themeService.mode();
    return mode === 'light' ? 'Tema claro (click para oscuro)'
      : mode === 'dark' ? 'Tema oscuro (click para automático)'
      : 'Tema automático (click para claro)';
  }

  protected cycleTheme(): void { this.themeService.toggleMode(); }
  protected toggleSidebar(): void { this.sidebarOpen.update(v => !v); }
}
