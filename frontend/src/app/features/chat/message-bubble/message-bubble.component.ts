/**
 * MessageBubbleComponent
 * ----------------------------------------------------------------------------
 * Renderiza una burbuja individual de mensaje. Cada mensaje en la lista
 * (usuario o bot) se renderiza con este componente.
 *
 * Variantes visuales:
 *   - role 'user'      → burbuja a la derecha, sin avatar.
 *   - role 'assistant' → burbuja a la izquierda, con avatar del bot.
 *   - status 'error'   → estilo de error + botón "Reintentar".
 *   - status 'cancelled' → estilo grisado + texto "Cancelado".
 *   - status 'done' (bot) → muestra botón "Copiar".
 *
 * Inputs:
 *   - message: el mensaje a renderizar.
 *
 * Outputs:
 *   - retryClicked: el usuario clickeó "Reintentar" (lo maneja la página padre).
 */
import {
  Component, input, output, signal, ChangeDetectionStrategy,
} from '@angular/core';
import { NgClass } from '@angular/common';
import { Message } from '../../../core/models/message.model';
import { RelativeTimePipe } from '../../../shared/pipes/relative-time.pipe';
import { ConfigService } from '../../../core/services/config.service';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [NgClass, RelativeTimePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './message-bubble.component.html',
  styleUrls: ['./message-bubble.component.scss'],
})
export class MessageBubbleComponent {
  // --- Inputs / Outputs ---
  readonly message = input.required<Message>();
  readonly retryClicked = output<void>();

  /** Lo usamos en el template para mostrar las iniciales del avatar del bot. */
  protected readonly config = new ConfigService();

  /** True durante 1.5s después de copiar — sirve para mostrar el ícono de tilde. */
  protected readonly copied = signal(false);

  /**
   * Copia el contenido del mensaje al portapapeles y muestra feedback visual.
   * Si el navegador no soporta clipboard.writeText, simplemente no hace nada
   * (no rompe la UI).
   */
  protected copyContent(): void {
    const content = this.message().content;
    navigator.clipboard.writeText(content).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }
}
