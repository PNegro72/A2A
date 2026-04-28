/**
 * LoggerService
 * ----------------------------------------------------------------------------
 * Wrapper sobre console.* con niveles y prefijo "[Sape]".
 * Filtra por nivel: en dev muestra todo (desde 'debug'), en prod
 * sólo muestra 'warn' y 'error'.
 *
 * Uso:
 *   const logger = inject(LoggerService);
 *   logger.debug('mensaje', { extra: 'data' });
 *   logger.error('algo falló', err);
 */
import { Injectable, isDevMode } from '@angular/core';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_RANK: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

@Injectable({ providedIn: 'root' })
export class LoggerService {
  private readonly minLevel: LogLevel = isDevMode() ? 'debug' : 'warn';

  debug(message: string, ...args: unknown[]): void {
    this.log('debug', message, ...args);
  }

  info(message: string, ...args: unknown[]): void {
    this.log('info', message, ...args);
  }

  warn(message: string, ...args: unknown[]): void {
    this.log('warn', message, ...args);
  }

  error(message: string, ...args: unknown[]): void {
    this.log('error', message, ...args);
  }

  private log(level: LogLevel, message: string, ...args: unknown[]): void {
    if (LEVEL_RANK[level] < LEVEL_RANK[this.minLevel]) return;

    const prefix = `[Sape][${level.toUpperCase()}]`;
    const consoleFn = level === 'error' ? console.error
      : level === 'warn' ? console.warn
      : level === 'info' ? console.info
      : console.debug;

    consoleFn(prefix, message, ...args);
  }
}
