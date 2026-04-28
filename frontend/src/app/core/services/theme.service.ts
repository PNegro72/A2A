/**
 * ThemeService
 * ----------------------------------------------------------------------------
 * Maneja el tema visual (claro / oscuro / automático según sistema).
 *
 * Conceptos:
 *   - mode:           preferencia del usuario ('light' | 'dark' | 'system').
 *   - resolvedTheme:  el tema realmente aplicado ('light' | 'dark').
 *                     Si mode === 'system', refleja la preferencia del SO.
 *
 * Mecanismos:
 *   - Persiste el mode elegido en localStorage (clave 'sape-theme').
 *   - Escucha cambios de la media query 'prefers-color-scheme: dark' del SO
 *     para reaccionar cuando el usuario cambia el tema del sistema en vivo.
 *   - Un effect() escribe el atributo `data-theme` en <html> cada vez que
 *     cambia el resolvedTheme — los estilos CSS leen ese atributo.
 *
 * Anti-flash: el archivo index.html tiene un script inline que aplica el
 * data-theme ANTES de que Angular bootee, para que no se vea el flash
 * blanco al cargar con tema oscuro.
 */
import { Injectable, signal, computed, effect } from '@angular/core';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'sape-theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly systemPreference = signal<ResolvedTheme>('light');
  readonly mode = signal<ThemeMode>('system');

  readonly resolvedTheme = computed<ResolvedTheme>(() => {
    const m = this.mode();
    return m === 'system' ? this.systemPreference() : m;
  });

  private mediaQuery: MediaQueryList | null = null;

  constructor() {
    // El effect() debe registrarse en el injection context del constructor.
    // Si se crea dentro de init() (llamado desde ngOnInit) Angular tira NG0203
    // y el tema no se aplica al DOM.
    effect(() => {
      document.documentElement.setAttribute('data-theme', this.resolvedTheme());
    });
  }

  /**
   * Inicializa el servicio. Se debe llamar UNA vez al arrancar la app
   * (lo hace ChatPageComponent.ngOnInit).
   */
  init(): void {
    // Detectar preferencia del sistema
    this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    this.systemPreference.set(this.mediaQuery.matches ? 'dark' : 'light');
    this.mediaQuery.addEventListener('change', (e) => {
      this.systemPreference.set(e.matches ? 'dark' : 'light');
    });

    // Cargar modo guardado
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
    if (saved && ['light', 'dark', 'system'].includes(saved)) {
      this.mode.set(saved);
    }
  }

  /** Setea explícitamente un modo y lo persiste. */
  setMode(mode: ThemeMode): void {
    this.mode.set(mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }

  /**
   * Cicla al siguiente modo: light → dark → system → light.
   * Es la acción del botón sol/luna del header.
   */
  toggleMode(): void {
    const current = this.mode();
    const next: ThemeMode = current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light';
    this.setMode(next);
  }
}
