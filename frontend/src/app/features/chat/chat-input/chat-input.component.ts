/**
 * ChatInputComponent
 * ----------------------------------------------------------------------------
 * Caja de texto para escribir el mensaje, con botón de enviar/detener
 * y soporte para adjuntar archivos (PDF, Word) para análisis de CV.
 *
 * Inputs:
 *   - isThinking: indica si el bot está respondiendo.
 *
 * Outputs:
 *   - messageSent: emite el texto del mensaje cuando el usuario envía.
 *   - stopClicked: emite cuando el usuario clickea "detener".
 *   - fileSent: emite { text, file, fileName } cuando se adjunta un archivo.
 */
import {
  Component, output, input, ElementRef, ViewChild,
  ChangeDetectionStrategy, AfterViewInit, signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

export interface MessageWithFile {
  text: string;
  fileBase64: string;
  fileName: string;
  mimeType: string;
}

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './chat-input.component.html',
  styleUrls: ['./chat-input.component.scss'],
})
export class ChatInputComponent implements AfterViewInit {
  readonly isThinking = input.required<boolean>();
  readonly messageSent = output<string>();
  readonly stopClicked = output<void>();
  readonly fileSent    = output<MessageWithFile>();

  @ViewChild('textarea')  private textareaRef!: ElementRef<HTMLTextAreaElement>;
  @ViewChild('fileInput') private fileInputRef!: ElementRef<HTMLInputElement>;

  protected text = '';

  /** Nombre del archivo adjunto (null si no hay archivo). */
  protected attachedFileName = signal<string | null>(null);
  private attachedFile: File | null = null;

  protected canSend(): boolean {
    return this.text.trim().length > 0 || this.attachedFile !== null;
  }

  ngAfterViewInit(): void {
    this.textareaRef.nativeElement.focus();
  }

  protected handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (this.canSend() && !this.isThinking()) {
        this.send();
      }
    }
  }

  protected handleSubmit(event: Event): void {
    event.preventDefault();
    if (this.canSend() && !this.isThinking()) {
      this.send();
    }
  }

  /** Abre el selector de archivos. */
  protected openFilePicker(): void {
    this.fileInputRef.nativeElement.click();
  }

  /** Maneja la selección de un archivo. */
  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file  = input.files?.[0];
    if (!file) return;

    this.attachedFile = file;
    this.attachedFileName.set(file.name);

    // Limpiar el input para que pueda seleccionarse el mismo archivo de nuevo
    input.value = '';
  }

  /** Elimina el archivo adjunto. */
  protected removeAttachment(): void {
    this.attachedFile = null;
    this.attachedFileName.set(null);
  }

  private send(): void {
    const msg = this.text.trim();

    if (this.attachedFile) {
      // Leer el archivo como base64 y emitir fileSent
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        this.fileSent.emit({
          text:       msg || `Analizá este CV: ${this.attachedFile!.name}`,
          fileBase64: base64,
          fileName:   this.attachedFile!.name,
          mimeType:   this.attachedFile!.type,
        });
        this.reset();
      };
      reader.readAsDataURL(this.attachedFile);
    } else {
      this.messageSent.emit(msg);
      this.reset();
    }
  }

  private reset(): void {
    this.text = '';
    this.attachedFile = null;
    this.attachedFileName.set(null);
    this.resetHeight();
  }

  protected autoResize(): void {
    const el = this.textareaRef.nativeElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 144) + 'px';
  }

  private resetHeight(): void {
    if (this.textareaRef?.nativeElement) {
      this.textareaRef.nativeElement.style.height = 'auto';
    }
  }

  focus(): void {
    this.textareaRef?.nativeElement.focus();
  }
}
