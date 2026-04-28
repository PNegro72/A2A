/**
 * OrchestratorService
 * ----------------------------------------------------------------------------
 * Cliente HTTP para hablar con el backend orchestrator (FastAPI corriendo
 * en `localhost:8000` por defecto, ver ConfigService / environment.ts).
 *
 * El flujo de un mensaje siempre tiene 2 pasos:
 *
 *   1. POST /chat            → crea el request y devuelve { request_id, ... }.
 *   2. Stream de respuesta   → según TRANSPORT_MODE en config:
 *        - 'sse'     → conecta a EventSource sobre /chat/stream/{requestId}
 *                      y recibe eventos 'step', 'final', 'error'.
 *        - 'polling' → hace GET /chat/status/{requestId} cada N ms hasta
 *                      que el status sea 'done' o 'error'.
 *
 * Ambos transportes terminan emitiendo el mismo tipo común StreamItem
 * (con type 'step' | 'final' | 'error'), así el componente que consume
 * NO necesita saber si es SSE o polling — sólo se suscribe al Observable.
 *
 * Errores HTTP se traducen a mensajes amigables en castellano via
 * mapHttpError (ver al final del archivo).
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, interval } from 'rxjs';
import { switchMap, takeWhile, map, catchError } from 'rxjs/operators';
import { ConfigService } from './config.service';
import { LoggerService } from './logger.service';
import {
  StreamInitResponse,
  StreamItem,
  AgentStep,
  FinalMessage,
  StreamError,
} from '../models/agent-step.model';

interface ChatRequest {
  conversation_id?: string;
  message: string;
}

interface PollingResponse {
  status: 'running' | 'done' | 'error';
  steps: AgentStep[];
  final?: FinalMessage;
  error?: StreamError;
}

@Injectable({ providedIn: 'root' })
export class OrchestratorService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ConfigService);
  private readonly logger = inject(LoggerService);

  /**
   * Envía un mensaje al orchestrator y retorna un StreamInitResponse
   * con el request_id para conectar al stream.
   *
   * Contrato POST /chat:
   * Request:  { conversation_id?: string, message: string }
   * Response: { conversation_id: string, request_id: string, stream_url: string }
   */
  sendMessage(conversationId: string | undefined, message: string): Observable<StreamInitResponse> {
    const body: ChatRequest = { message };
    if (conversationId) body.conversation_id = conversationId;

    this.logger.debug('OrchestratorService.sendMessage', { conversationId, message });

    return this.http.post<StreamInitResponse>(this.config.chatUrl(), body).pipe(
      catchError((err: HttpErrorResponse) => {
        this.logger.error('Error enviando mensaje', err);
        return throwError(() => this.mapHttpError(err));
      })
    );
  }

  /**
   * Conecta al stream de respuesta del orchestrator.
   * Usa SSE o polling según la configuración de TRANSPORT_MODE.
   */
  streamResponse(requestId: string): Observable<StreamItem> {
    this.logger.debug('OrchestratorService.streamResponse', { requestId, transport: this.config.transportMode });
    if (this.config.transportMode === 'sse') {
      return this.connectSSE(requestId);
    }
    return this.pollStatus(requestId);
  }

  /**
   * Conecta via Server-Sent Events.
   *
   * Contrato GET /chat/stream/{requestId}:
   * event: step  → data: AgentStep
   * event: final → data: FinalMessage
   * event: error → data: StreamError
   */
  private connectSSE(requestId: string): Observable<StreamItem> {
    const url = this.config.streamUrl(requestId);
    this.logger.debug('Conectando SSE', { url });

    return new Observable<StreamItem>((observer) => {
      const eventSource = new EventSource(url);

      eventSource.addEventListener('step', (event: Event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as AgentStep;
          data.timestamp = new Date(data.timestamp ?? Date.now());
          observer.next({ type: 'step', data });
        } catch (e) {
          this.logger.warn('Error parseando evento step', e);
        }
      });

      eventSource.addEventListener('final', (event: Event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as FinalMessage;
          observer.next({ type: 'final', data });
          eventSource.close();
          observer.complete();
        } catch (e) {
          this.logger.warn('Error parseando evento final', e);
        }
      });

      eventSource.addEventListener('error', (event: Event) => {
        // Si el eventSource tiene readyState CLOSED, es error del servidor
        if (eventSource.readyState === EventSource.CLOSED) {
          const streamErr: StreamError = { code: 'SSE_CLOSED', message: 'Conexión SSE cerrada inesperadamente' };
          observer.next({ type: 'error', data: streamErr });
          observer.error(new Error(streamErr.message));
          return;
        }
        try {
          const data = JSON.parse((event as MessageEvent).data) as StreamError;
          observer.next({ type: 'error', data });
          eventSource.close();
          observer.error(new Error(data.message));
        } catch {
          const streamErr: StreamError = { code: 'SSE_ERROR', message: 'Error en stream SSE' };
          observer.next({ type: 'error', data: streamErr });
          eventSource.close();
          observer.error(new Error(streamErr.message));
        }
      });

      // Teardown: cierra el EventSource al desuscribirse
      return () => {
        this.logger.debug('SSE teardown', { requestId });
        eventSource.close();
      };
    });
  }

  /**
   * Fallback: polling GET /chat/status/{requestId}
   * Acumula pasos y espera hasta que status === 'done' | 'error'.
   *
   * Contrato GET /chat/status/{requestId}:
   * Response: { status: 'running'|'done'|'error', steps: AgentStep[], final?: FinalMessage, error?: StreamError }
   */
  private pollStatus(requestId: string): Observable<StreamItem> {
    const url = this.config.statusUrl(requestId);
    let seenStepCount = 0;

    return interval(this.config.pollingIntervalMs).pipe(
      switchMap(() => this.http.get<PollingResponse>(url).pipe(
        catchError((err: HttpErrorResponse) => throwError(() => this.mapHttpError(err)))
      )),
      map((response) => {
        // Emite solo los pasos nuevos que no hayamos visto
        const newSteps = response.steps.slice(seenStepCount);
        seenStepCount = response.steps.length;

        const items: StreamItem[] = newSteps.map(step => ({
          type: 'step' as const,
          data: { ...step, timestamp: new Date(step.timestamp) },
        }));

        if (response.status === 'done' && response.final) {
          items.push({ type: 'final', data: response.final });
        } else if (response.status === 'error' && response.error) {
          items.push({ type: 'error', data: response.error });
        }

        return items;
      }),
      switchMap((items) => new Observable<StreamItem>((observer) => {
        items.forEach(item => observer.next(item));
        observer.complete();
      })),
      takeWhile((item) => item.type !== 'final' && item.type !== 'error', true),
    );
  }

  private mapHttpError(err: HttpErrorResponse): Error {
    if (err.status === 0) return new Error('Sin conexión con el servidor. Verificá que el orchestrator esté corriendo.');
    if (err.status === 503) return new Error('El orchestrator no está disponible (503).');
    if (err.status === 504) return new Error('Timeout del servidor (504). Reintentá en unos segundos.');
    return new Error(err.error?.message ?? `Error ${err.status}: ${err.statusText}`);
  }
}
