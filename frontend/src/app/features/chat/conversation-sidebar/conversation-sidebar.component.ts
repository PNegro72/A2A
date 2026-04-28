/**
 * ConversationSidebarComponent
 * ----------------------------------------------------------------------------
 * Sidebar lateral con la lista de conversaciones del usuario.
 *
 * Es un componente "tonto" (presentational): no toca el ConversationsService
 * directamente, todo lo que hace es emitir eventos al padre (ChatPageComponent),
 * que los traduce en llamadas al servicio.
 *
 * Inputs:
 *   - conversations: lista de conversaciones a mostrar.
 *   - activeId:      id de la conversación activa (para resaltarla).
 *   - open:          si la sidebar está abierta (afecta visibilidad en mobile).
 *
 * Outputs:
 *   - selectConversation: el usuario clickeó una conversación.
 *   - newConversation:    el usuario clickeó "Nueva".
 *   - deleteConversation: el usuario confirmó borrar (emite el id).
 *   - renameConversation: el usuario confirmó renombrar (emite { id, title }).
 *   - closeSidebar:       el usuario quiere cerrar la sidebar (overlay click).
 *
 * Estado interno:
 *   - renamingConv: cuando no es null, mostramos el modal de renombrar.
 *   - deletingId:   cuando no es null, mostramos el modal de confirmación de borrado.
 */
import {
  Component, input, output, signal, ChangeDetectionStrategy,
} from '@angular/core';
import { NgClass } from '@angular/common';
import { Conversation } from '../../../core/models/conversation.model';
import { RelativeTimePipe } from '../../../shared/pipes/relative-time.pipe';

@Component({
  selector: 'app-conversation-sidebar',
  standalone: true,
  imports: [NgClass, RelativeTimePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './conversation-sidebar.component.html',
  styleUrls: ['./conversation-sidebar.component.scss'],
})
export class ConversationSidebarComponent {
  // --- Inputs ---
  readonly conversations = input.required<Conversation[]>();
  readonly activeId = input<string | null>(null);
  readonly open = input.required<boolean>();

  // --- Outputs ---
  readonly selectConversation = output<string>();
  readonly newConversation = output<void>();
  readonly deleteConversation = output<string>();
  readonly renameConversation = output<{ id: string; title: string }>();
  readonly closeSidebar = output<void>();

  // --- Estado interno (modales) ---
  /** Conversación en proceso de renombrar (null = modal cerrado). */
  protected readonly renamingConv = signal<Conversation | null>(null);
  /** Id de la conversación pendiente de borrado (null = modal cerrado). */
  protected readonly deletingId = signal<string | null>(null);
  /** Valor actual del input del modal de renombre. */
  protected renameValue = '';

  // --- Renombrar ---

  /** Abre el modal de renombre, pre-cargando el título actual. */
  protected startRename(conv: Conversation): void {
    this.renamingConv.set(conv);
    this.renameValue = conv.title;
  }

  /** Cancela el renombre y cierra el modal. */
  protected cancelRename(): void {
    this.renamingConv.set(null);
    this.renameValue = '';
  }

  /** Confirma el renombre. Si el texto está vacío, no emite (pero igual cierra). */
  protected commitRename(): void {
    const conv = this.renamingConv();
    if (conv && this.renameValue.trim()) {
      this.renameConversation.emit({ id: conv.id, title: this.renameValue.trim() });
    }
    this.cancelRename();
  }

  // --- Eliminar ---

  /** Abre el modal de confirmación de borrado. */
  protected confirmDelete(id: string): void {
    this.deletingId.set(id);
  }

  /** Cancela el borrado. */
  protected cancelDelete(): void {
    this.deletingId.set(null);
  }

  /** Confirma el borrado: emite el id al padre y cierra el modal. */
  protected commitDelete(): void {
    const id = this.deletingId();
    if (id) this.deleteConversation.emit(id);
    this.deletingId.set(null);
  }
}
