/**
 * URL base de Odoo — configurable en tiempo de ejecución.
 * Prioridad: localStorage → variable de entorno → fallback localhost
 */

const ENV_URL = process.env.NEXT_PUBLIC_ODOO_URL || 'http://localhost:8069';

export const ODOO_URL_KEY = 'bim_odoo_url';

export function getOdooBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(ODOO_URL_KEY);
    if (stored) return stored.replace(/\/$/, '');
  }
  return ENV_URL.replace(/\/$/, '');
}

export function setOdooBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(ODOO_URL_KEY, url.replace(/\/$/, ''));
  }
}

export function clearOdooBaseUrl(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(ODOO_URL_KEY);
  }
}
