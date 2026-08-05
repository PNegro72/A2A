/**
 * OrchestratorService
 * ----------------------------------------------------------------------------
 * Cliente HTTP para hablar con el backend orchestrator.
 * Soporta mensajes de texto y mensajes con archivos adjuntos (CV en PDF/Word).
 */
import { MessageWithFiles } from '../../features/chat/chat-input/chat-input.component';
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
  file?: {
    base64: string;
    fileName: string;
    mimeType: string;
  };
}

interface PollingResponse {
  status: 'running' | 'done' | 'error';
  steps: AgentStep[];
  final?: FinalMessage;
  error?: StreamError;
}

@Injectable({ providedIn: 'root' })
export class OrchestratorService {
  private readonly http   = inject(HttpClient);
  private readonly config = inject(ConfigService);
  private readonly logger = inject(LoggerService);

  /**
   * Envía un mensaje de texto al orchestrator.
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
   * Envía un mensaje con archivo adjunto (CV en PDF/Word).
   * El archivo se incluye como base64 en el payload.
   */
sendMessageWithFiles(conversationId: string | undefined, payload: MessageWithFiles): Observable<StreamInitResponse> {
  const body = {
    message: payload.text,
    files: payload.files.map(f => ({
      base64:   f.fileBase64,
      fileName: f.fileName,
      mimeType: f.mimeType,
    })),
    conversation_id: conversationId,
  };
 
  this.logger.debug('OrchestratorService.sendMessageWithFiles', {
    conversationId,
    fileCount: payload.files.length,
  });
 
  return this.http.post<StreamInitResponse>(this.config.chatUrl(), body).pipe(
    catchError((err: HttpErrorResponse) => {
      this.logger.error('Error enviando mensaje con archivos', err);
      return throwError(() => this.mapHttpError(err));
    })
  );
}

  /**
   * Conecta al stream de respuesta del orchestrator.
   */
  streamResponse(requestId: string): Observable<StreamItem> {
    this.logger.debug('OrchestratorService.streamResponse', { requestId, transport: this.config.transportMode });
    if (this.config.transportMode === 'sse') {
      return this.connectSSE(requestId);
    }
    return this.pollStatus(requestId);
  }

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

      return () => {
        this.logger.debug('SSE teardown', { requestId });
        eventSource.close();
      };
    });
  }

  private pollStatus(requestId: string): Observable<StreamItem> {
    const url = this.config.statusUrl(requestId);
    let seenStepCount = 0;

    return interval(this.config.pollingIntervalMs).pipe(
      switchMap(() => this.http.get<PollingResponse>(url).pipe(
        catchError((err: HttpErrorResponse) => throwError(() => this.mapHttpError(err)))
      )),
      map((response) => {
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
