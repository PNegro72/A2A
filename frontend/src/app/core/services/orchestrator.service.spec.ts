import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { OrchestratorService } from './orchestrator.service';
import { ConfigService } from './config.service';

describe('OrchestratorService', () => {
  let service: OrchestratorService;
  let httpMock: HttpTestingController;
  let config: ConfigService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        OrchestratorService,
        ConfigService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(OrchestratorService);
    httpMock = TestBed.inject(HttpTestingController);
    config = TestBed.inject(ConfigService);
  });

  afterEach(() => httpMock.verify());

  it('debería crearse correctamente', () => {
    expect(service).toBeTruthy();
  });

  it('sendMessage() debería hacer POST al endpoint correcto', (done) => {
    const mockResponse = {
      conversation_id: 'conv-123',
      request_id: 'req-abc',
      stream_url: '/chat/stream/req-abc',
    };

    service.sendMessage('conv-123', 'Buscar candidatos para React').subscribe((res) => {
      expect(res.conversation_id).toBe('conv-123');
      expect(res.request_id).toBe('req-abc');
      done();
    });

    const req = httpMock.expectOne(config.chatUrl());
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      conversation_id: 'conv-123',
      message: 'Buscar candidatos para React',
    });
    req.flush(mockResponse);
  });

  it('sendMessage() sin conversation_id no debería enviar el campo', () => {
    service.sendMessage(undefined, 'Hola').subscribe();

    const req = httpMock.expectOne(config.chatUrl());
    expect(req.request.body).toEqual({ message: 'Hola' });
    expect(req.request.body.conversation_id).toBeUndefined();
    req.flush({ conversation_id: 'new', request_id: 'r1', stream_url: '/chat/stream/r1' });
  });

  it('sendMessage() debería emitir error amigable si el servidor falla', (done) => {
    service.sendMessage(undefined, 'test').subscribe({
      error: (err: Error) => {
        expect(err.message).toContain('503');
        done();
      },
    });

    const req = httpMock.expectOne(config.chatUrl());
    req.flush({ message: 'Service unavailable' }, { status: 503, statusText: 'Service Unavailable' });
  });
});
