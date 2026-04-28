/**
 * ThinkingIndicatorComponent
 * ----------------------------------------------------------------------------
 * Indicador visual que se muestra mientras el bot procesa la respuesta.
 *
 * Cuando el orchestrator emite "pasos intermedios" (cada agente que va
 * trabajando, tipo "Buscando candidatos en ATS...", "Generando preguntas..."),
 * este componente los recibe y los muestra:
 *   - Por defecto colapsado: solo se ve el último paso.
 *   - Al hacer click se expande mostrando todos los pasos con su status.
 *
 * Inputs:
 *   - steps: array de pasos del agente (los va alimentando ChatPageComponent
 *     a medida que llegan por el stream).
 */
import {
  Component, input, signal, computed, ChangeDetectionStrategy,
} from '@angular/core';
import { NgClass } from '@angular/common';
import { AgentStep } from '../../../core/models/agent-step.model';
import { ConfigService } from '../../../core/services/config.service';

@Component({
  selector: 'app-thinking-indicator',
  standalone: true,
  imports: [NgClass],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './thinking-indicator.component.html',
  styleUrls: ['./thinking-indicator.component.scss'],
})
export class ThinkingIndicatorComponent {
  // --- Inputs ---
  readonly steps = input.required<AgentStep[]>();

  /** Se usa solo para mostrar las iniciales del avatar del bot. */
  protected readonly config = new ConfigService();

  /** Si la lista detallada de pasos está visible o colapsada. */
  protected readonly expanded = signal(false);

  /** El último paso emitido (el que está "activo" ahora) — se muestra siempre. */
  protected readonly lastStep = computed(() => {
    const all = this.steps();
    return all.length > 0 ? all[all.length - 1] : null;
  });

  /**
   * Alto estimado del contenedor de pasos para animar la expansión.
   * Usamos ~36px por paso + 16px de padding. No es preciso al pixel,
   * pero alcanza porque después el contenedor se ajusta solo.
   */
  protected readonly stepsHeight = computed(() => {
    const count = this.steps().length;
    return `${count * 36 + 16}px`;
  });

  /**
   * Toggle expandir/colapsar. Solo aplica si hay al menos un paso —
   * sino no tiene sentido expandir nada.
   */
  protected toggle(): void {
    if (this.steps().length > 0) {
      this.expanded.update(v => !v);
    }
  }
}
