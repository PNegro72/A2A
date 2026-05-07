/**
 * MessageBubbleComponent
 * ----------------------------------------------------------------------------
 * Renderiza una burbuja individual de mensaje.
 * Si el mensaje del bot contiene una URL de descarga del kit
 * (http://localhost:8003/download/...), la extrae y muestra un botón de descarga.
 */
import {
  Component, input, output, signal, computed, ChangeDetectionStrategy,
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
  readonly message = input.required<Message>();
  readonly retryClicked = output<void>();
 
  protected readonly config = new ConfigService();
  protected readonly copied = signal(false);
 
  /**
   * Extrae la URL de descarga del kit si aparece en el contenido del mensaje.
   * El orquestador incluye algo como:
   *   "Kit generado: http://localhost:8003/download/kit_martina_20260507_1122.docx"
   * Si no hay URL, devuelve null.
   */
  protected readonly kitDownloadUrl = computed<string | null>(() => {
    const content = this.message().content;
    if (!content) return null;
    const match = content.match(/https?:\/\/[^\s]+\/download\/[^\s)]+\.docx/);
    return match ? match[0] : null;
  });
 
  protected copyContent(): void {
    const content = this.message().content;
    navigator.clipboard.writeText(content).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }
 
  protected downloadKit(): void {
    const url = this.kitDownloadUrl();
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = url.split('/').pop() ?? 'kit_entrevista.docx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}