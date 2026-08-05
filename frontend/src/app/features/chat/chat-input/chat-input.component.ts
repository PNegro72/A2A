/**
 * ChatInputComponent
 * ----------------------------------------------------------------------------
 * Caja de texto con soporte para:
 * - Un archivo o varios (carpeta de CVs) → emite filesSent
 */

import {
  Component, output, input, ElementRef, ViewChild,
  ChangeDetectionStrategy, AfterViewInit, signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

export interface MessageWithFiles {
  text: string;
  files: { fileBase64: string; fileName: string; mimeType: string }[];
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
  readonly isThinking  = input.required<boolean>();
  readonly messageSent = output<string>();
  readonly stopClicked = output<void>();
  readonly filesSent   = output<MessageWithFiles>();

  @ViewChild('textarea')      private textareaRef!:     ElementRef<HTMLTextAreaElement>;
  @ViewChild('fileInput')     private fileInputRef!:    ElementRef<HTMLInputElement>;
  @ViewChild('folderInput')   private folderInputRef!:  ElementRef<HTMLInputElement>;

  protected text = '';

  protected attachedFileName  = signal<string | null>(null);   // un archivo
  protected attachedFileCount = signal<number>(0);             // varios archivos
  private attachedFile:  File | null = null;
  private attachedFiles: File[]      = [];

  protected canSend(): boolean {
    return this.text.trim().length > 0
        || this.attachedFile  !== null
        || this.attachedFiles.length > 0;
  }

  ngAfterViewInit(): void {
    this.textareaRef.nativeElement.focus();
  }

  protected handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (this.canSend() && !this.isThinking()) this.send();
    }
  }

  protected handleSubmit(event: Event): void {
    event.preventDefault();
    if (this.canSend() && !this.isThinking()) this.send();
  }

  /** Abre el selector para un único archivo (CV individual). */
  protected openFilePicker(): void {
    this.fileInputRef.nativeElement.click();
  }

  /** Abre el selector para una carpeta de CVs. */
  protected openFolderPicker(): void {
    this.folderInputRef.nativeElement.click();
  }

  /** Maneja la selección de un único archivo. */
  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file  = input.files?.[0];
    if (!file) return;

    // Limpiar selección de carpeta si había
    this.attachedFiles = [];
    this.attachedFileCount.set(0);

    this.attachedFile = file;
    this.attachedFileName.set(file.name);
    input.value = '';
  }

  /** Maneja la selección de una carpeta con múltiples CVs. */
  protected onFolderSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = input.files;
    if (!files || files.length === 0) return;

    // Filtrar solo PDFs y Word
    const cvFiles = Array.from(files).filter(f =>
      f.type === 'application/pdf' ||
      f.type === 'application/msword' ||
      f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    );

    if (cvFiles.length === 0) {
      alert('No se encontraron archivos PDF o Word en la carpeta seleccionada.');
      return;
    }

    // Limpiar selección de archivo único si había
    this.attachedFile = null;
    this.attachedFileName.set(null);

    this.attachedFiles = cvFiles;
    this.attachedFileCount.set(cvFiles.length);
    input.value = '';
  }

  /** Elimina el archivo adjunto individual. */
  protected removeAttachment(): void {
    this.attachedFile = null;
    this.attachedFileName.set(null);
  }

  /** Elimina la carpeta adjunta. */
  protected removeFolderAttachment(): void {
    this.attachedFiles = [];
    this.attachedFileCount.set(0);
  }

  private send(): void {
    const msg = this.text.trim();

    if (this.attachedFiles.length > 0) {
      // Múltiples CVs — leer todos como base64 y emitir filesSent
      this._readMultipleFiles(msg);
    } else if (this.attachedFile) {
      // Un solo CV
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        this.filesSent.emit({
          text:  msg || `Analizá este CV: ${this.attachedFile!.name}`,
          files: [{
            fileBase64: base64,
            fileName:   this.attachedFile!.name,
            mimeType:   this.attachedFile!.type,
          }],
        });
        this.reset();
      };
      reader.readAsDataURL(this.attachedFile);
    } else {
      this.messageSent.emit(msg);
      this.reset();
    }
  }

  private _readMultipleFiles(msg: string): void {
    const files   = this.attachedFiles;
    const results: { fileBase64: string; fileName: string; mimeType: string }[] = [];
    let   pending = files.length;

    files.forEach((file, index) => {
      const reader = new FileReader();
      reader.onload = () => {
        results[index] = {
          fileBase64: (reader.result as string).split(',')[1],
          fileName:   file.name,
          mimeType:   file.type,
        };
        pending--;
        if (pending === 0) {
          this.filesSent.emit({
            text:  msg || `Rankear estos ${files.length} CVs contra el Job Description`,
            files: results,
          });
          this.reset();
        }
      };
      reader.readAsDataURL(file);
    });
  }

  private reset(): void {
    this.text = '';
    this.attachedFile  = null;
    this.attachedFiles = [];
    this.attachedFileName.set(null);
    this.attachedFileCount.set(0);
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