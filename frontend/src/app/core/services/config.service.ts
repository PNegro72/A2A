/**
 * ConfigService
 * ----------------------------------------------------------------------------
 * Centraliza la configuración de la aplicación. Lee los valores del archivo
 * de environment (src/environments/environment.ts y environment.prod.ts)
 * y los expone como propiedades + helpers para construir URLs.
 *
 * Si necesitás cambiar la URL del orchestrator, el nombre del agente, el
 * modo de transporte (sse/polling) o los timeouts, hacelo en environment.ts,
 * NO en este archivo.
 * 
 * ##
 */

import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ConfigService {
  readonly orchestratorBaseUrl = environment.orchestratorBaseUrl;
  readonly chatEndpoint = environment.chatEndpoint;
  readonly streamEndpoint = environment.streamEndpoint;
  readonly agentName = environment.agentName;
  readonly agentTagline = environment.agentTagline;
  readonly agentAvatarInitials = environment.agentAvatarInitials;
  readonly transportMode = environment.transportMode;
  readonly pollingIntervalMs = environment.pollingIntervalMs;
  readonly requestTimeoutMs = environment.requestTimeoutMs;

  /** URL completa para POST /chat. */
  chatUrl(): string {
    return `${this.orchestratorBaseUrl}${this.chatEndpoint}`;
  }

  /** URL completa para conectarse al SSE de un request específico. */
  streamUrl(requestId: string): string {
    return `${this.orchestratorBaseUrl}${this.streamEndpoint}/${requestId}`;
  }

  /** URL para hacer polling del status de un request (modo fallback). */
  statusUrl(requestId: string): string {
    return `${this.orchestratorBaseUrl}/chat/status/${requestId}`;
  }
}
