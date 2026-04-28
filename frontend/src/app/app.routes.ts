/**
 * Rutas de la aplicación.
 * ----------------------------------------------------------------------------
 *   - "/"      → redirige a /chat
 *   - "/chat"  → carga ChatPageComponent (lazy: el bundle del chat se baja
 *                bajo demanda).
 *   - "**"     → cualquier URL desconocida también va a /chat.
 *
 * Por ahora la app tiene una sola pantalla (el chat). Si en el futuro
 * agregás más pantallas (ej. /settings, /admin), declarálas acá.
 */
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'chat',
    pathMatch: 'full',
  },
  {
    path: 'chat',
    loadComponent: () =>
      import('./features/chat/chat-page/chat-page.component').then(
        (m) => m.ChatPageComponent
      ),
  },
  {
    path: '**',
    redirectTo: 'chat',
  },
];
