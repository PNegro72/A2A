/**
 * ChatInputComponent
 * ----------------------------------------------------------------------------
 * Caja de texto para escribir el mensaje, con botón de enviar/detener.
 *
 * Inputs:
 *   - isThinking: indica si el bot está respondiendo (deshabilita el textarea
 *     y muestra el botón "detener" en lugar del de "enviar").
 *
 * Outputs:
 *   - messageSent: emite el texto del mensaje cuando el usuario envía.
 *   - stopClicked: emite cuando el usuario clickea "detener".
 *
 * Detalles UX:
 *   - El textarea crece automáticamente con el contenido (hasta 144px ≈ 6 líneas).
 *   - Enter envía, Shift+Enter inserta nueva línea.
 *   - Al montarse, el textarea recibe foco automáticamente.
 */
import {
  Component, output, input, ElementRef, ViewChild,
  ChangeDetectionStrategy, AfterViewInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './chat-input.component.html',
  styleUrls: ['./chat-input.component.scss'],
})
export class ChatInputComponent implements AfterViewInit {
  // --- Inputs / Outputs ---
  readonly isThinking = input.required<boolean>();
  readonly messageSent = output<string>();
  readonly stopClicked = output<void>();

  /** Referencia al elemento <textarea> para poder ajustar su altura y darle foco. */
  @ViewChild('textarea') private textareaRef!: ElementRef<HTMLTextAreaElement>;

  /** Texto actual del input (bound con ngModel). */
  protected text = '';

  /** True solo si hay algo escrito (sin contar espacios) — habilita el botón enviar. */
  protected canSend(): boolean {
    return this.text.trim().length > 0;
  }

  ngAfterViewInit(): void {
    // Damos foco al textarea apenas se renderiza así el usuario puede escribir directo.
    this.textareaRef.nativeElement.focus();
  }

  /**
   * Maneja teclas en el textarea:
   *   - Enter (sin Shift): envía el mensaje.
   *   - Shift+Enter: deja que el textarea inserte una nueva línea normalmente.
   */
  protected handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (this.canSend() && !this.isThinking()) {
        this.send();
      }
    }
  }

  /** Submit del <form>: equivalente a click en el botón "enviar". */
  protected handleSubmit(event: Event): void {
    event.preventDefault();
    if (this.canSend() && !this.isThinking()) {
      this.send();
    }
  }

  /** Emite el mensaje al padre y limpia el textarea. */
  private send(): void {
    const msg = this.text.trim();
    this.text = '';
    this.resetHeight();
    this.messageSent.emit(msg);
  }

  /**
   * Ajusta la altura del textarea al alto de su contenido (con tope máximo).
   * Se llama en cada (input). Truco común: poner height='auto' primero
   * para que scrollHeight refleje el alto real, y después fijarlo.
   */
  protected autoResize(): void {
    const el = this.textareaRef.nativeElement;
    el.style.height = 'auto';
    // Tope máximo ≈ 6 líneas (144px con line-height 1.5 y font 16px).
    const maxHeight = 144;
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px';
  }

  /** Vuelve la altura del textarea a una sola línea (después de enviar). */
  private resetHeight(): void {
    if (this.textareaRef?.nativeElement) {
      const el = this.textareaRef.nativeElement;
      el.style.height = 'auto';
    }
  }

  /** Permite al padre forzar foco en el textarea (p. ej. tras seleccionar conversación). */
  focus(): void {
    this.textareaRef?.nativeElement.focus();
  }
}
