/**
 * RelativeTimePipe
 * ----------------------------------------------------------------------------
 * Pipe que formatea una fecha como tiempo relativo en castellano:
 *   "ahora", "hace 12s", "hace 5 min", "hace 3h", "hace 2d", "27 abr"
 *
 * Se usa en las burbujas de mensaje y en la lista de conversaciones.
 *
 * Es `pure: false` para que se actualice automáticamente con cada
 * change-detection (sin esto, "ahora" se quedaría congelado y no
 * pasaría a "hace 1 min" salvo que cambie la referencia del input).
 *
 * Uso en template:
 *   {{ message.timestamp | relativeTime }}
 */
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'relativeTime', standalone: true, pure: false })
export class RelativeTimePipe implements PipeTransform {
  transform(value: Date | string | null | undefined): string {
    if (!value) return '';

    const date = typeof value === 'string' ? new Date(value) : value;
    if (isNaN(date.getTime())) return '';

    const now = Date.now();
    const diffMs = now - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSec < 30) return 'ahora';
    if (diffSec < 60) return `hace ${diffSec}s`;
    if (diffMin < 60) return `hace ${diffMin} min`;
    if (diffHours < 24) return `hace ${diffHours}h`;
    if (diffDays < 7) return `hace ${diffDays}d`;

    return date.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' });
  }
}
