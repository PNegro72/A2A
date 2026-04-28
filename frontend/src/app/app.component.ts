/**
 * AppComponent
 * ----------------------------------------------------------------------------
 * Componente raíz de la aplicación Angular. Es el primer componente que
 * Angular monta cuando arranca el bootstrap (ver main.ts).
 *
 * Su única responsabilidad es exponer un <router-outlet> donde el Router
 * inserta la página correspondiente a la URL actual. La lógica del chat,
 * la sidebar, el tema, etc. vive en los componentes hijos cargados por
 * el router (ver app.routes.ts).
 */
import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './app.component.html',
})
export class AppComponent {}
