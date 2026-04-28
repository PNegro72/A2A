/**
 * MessageListComponent
 * ----------------------------------------------------------------------------
 * Lista scrolleable de mensajes de la conversación activa, con auto-scroll
 * inteligente y un botón flotante para "volver al final".
 *
 * Inputs:
 *   - messages:   array de mensajes a mostrar.
 *   - isThinking: si está esperando respuesta (muestra indicador "Pensando").
 *   - agentSteps: pasos intermedios del agente (los pasa al ThinkingIndicator).
 *
 * Outputs:
 *   - retryClicked: el usuario clickeó "Reintentar" en un mensaje con error.
 *
 * Comportamiento de scroll:
 *   - Si el usuario está pegado al final, hacemos auto-scroll cuando llegan
 *     mensajes nuevos.
 *   - Si el usuario scrolleó hacia arriba a leer algo, NO interrumpimos su
 *     lectura: en su lugar mostramos un botón flotante "Nuevos mensajes".
 *   - "Estar al final" se considera con un margen de tolerancia de 80px.
 */
import {
  Component, input, output, signal, ElementRef, ViewChild,
  ChangeDetectionStrategy, AfterViewChecked, OnChanges,
} from '@angular/core';
import { Message } from '../../../core/models/message.model';
import { AgentStep } from '../../../core/models/agent-step.model';
import { MessageBubbleComponent } from '../message-bubble/message-bubble.component';
import { ThinkingIndicatorComponent } from '../thinking-indicator/thinking-indicator.component';

@Component({
  selector: 'app-message-list',
  standalone: true,
  imports: [MessageBubbleComponent, ThinkingIndicatorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './message-list.component.html',
  styleUrls: ['./message-list.component.scss'],
})
export class MessageListComponent implements AfterViewChecked, OnChanges {
  // --- Inputs / Outputs ---
  readonly messages = input.required<Message[]>();
  readonly isThinking = input.required<boolean>();
  readonly agentSteps = input.required<AgentStep[]>();
  readonly retryClicked = output<void>();

  /** Contenedor con scroll: lo usamos para detectar si el usuario está al final. */
  @ViewChild('scrollContainer') private scrollContainer!: ElementRef<HTMLElement>;
  /** Ancla invisible al final de la lista: target del scrollIntoView. */
  @ViewChild('bottomAnchor') private bottomAnchor!: ElementRef<HTMLElement>;

  /** Controla la visibilidad del botón flotante "Nuevos mensajes". */
  protected readonly showScrollBtn = signal(false);
  /** True si el usuario scrolleó hacia arriba (no queremos pisar su lectura). */
  private userScrolledUp = false;
  /** Para detectar cuándo cambió la cantidad de mensajes. */
  private prevMessageCount = 0;

  ngOnChanges(): void {
    // Sólo reaccionamos cuando cambia la cantidad de mensajes (no por cualquier
    // otro cambio de inputs como isThinking o agentSteps).
    const currentCount = this.messages().length;
    if (currentCount !== this.prevMessageCount) {
      this.prevMessageCount = currentCount;
      if (!this.userScrolledUp) {
        // Usuario al final → seguimos pegados al final
        this.scheduleScrollToBottom();
      } else {
        // Usuario leyendo algo más arriba → mostramos el botón "Nuevos mensajes"
        this.showScrollBtn.set(true);
      }
    }
  }

  ngAfterViewChecked(): void {
    // Mantener pegado al final mientras se va construyendo el DOM (los mensajes
    // pueden aumentar de alto a medida que se renderiza el contenido).
    if (!this.userScrolledUp) {
      this.doScrollToBottom();
    }
  }

  /**
   * Cada vez que el usuario scrollea, recalculamos si está pegado al final
   * (con tolerancia de 80px). Esto define si haremos auto-scroll o no.
   */
  protected onScroll(): void {
    const el = this.scrollContainer.nativeElement;
    const threshold = 80;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    this.userScrolledUp = distFromBottom > threshold;

    // Si volvió al final manualmente, ocultamos el botón flotante
    if (!this.userScrolledUp) {
      this.showScrollBtn.set(false);
    }
  }

  /** Acción del botón flotante "Nuevos mensajes": scrollea al final. */
  protected scrollToBottom(): void {
    this.userScrolledUp = false;
    this.showScrollBtn.set(false);
    this.doScrollToBottom();
  }

  /**
   * Defer de 50ms: damos tiempo a Angular a renderizar el nuevo mensaje
   * antes de intentar scrollear, sino el scrollIntoView no llega al fondo real.
   */
  private scheduleScrollToBottom(): void {
    setTimeout(() => this.scrollToBottom(), 50);
  }

  private doScrollToBottom(): void {
    this.bottomAnchor?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}
