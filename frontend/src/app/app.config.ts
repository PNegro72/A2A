/**
 * appConfig
 * ----------------------------------------------------------------------------
 * Configuración de la aplicación que se pasa a bootstrapApplication() en main.ts.
 * Acá registramos los providers globales que estarán disponibles en toda la app:
 *
 *   - provideZoneChangeDetection: optimización de change detection
 *     (eventCoalescing junta múltiples eventos en un solo ciclo).
 *   - provideRouter: el router con las rutas definidas en app.routes.ts.
 *     withComponentInputBinding permite recibir parámetros de la URL como
 *     @Input() en los componentes.
 *   - provideHttpClient(withFetch()): HttpClient usando la API Fetch nativa
 *     (en vez de XMLHttpRequest), recomendado en Angular moderno.
 *   - provideServiceWorker: registra el service worker para PWA. Se desactiva
 *     en modo dev para no entorpecer el HMR.
 */
import {
  ApplicationConfig,
  provideZoneChangeDetection,
  isDevMode,
} from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideServiceWorker } from '@angular/service-worker';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch()),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
