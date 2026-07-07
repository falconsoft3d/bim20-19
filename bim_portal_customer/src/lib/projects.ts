/**
 * Servicio para obtener proyectos BIM del usuario autenticado.
 */

import { getOdooBaseUrl } from '@/lib/odoo';

export interface BimProject {
  id: number;
  name: string;
  nombre: string;
  state: string;
  balance: number;
  sale_total: number;
  cost_total: number;
  profit: number;
  margin: number;
  budgeted_hours: number;
  real_hours: number;
  currency: string;
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchProjects(): Promise<BimProject[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/projects`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.projects as BimProject[]) : [];
}

export async function fetchProject(id: number): Promise<BimProject | null> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/projects/${id}`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? (data.project as BimProject) : null;
}

// ── Helpers de formato ────────────────────────────────────────────────────────

export function fmtCurrency(value: number, symbol = '€'): string {
  if (Math.abs(value) >= 1000) {
    return `${symbol}${(value / 1000).toFixed(1)}k`;
  }
  return `${symbol}${value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtHours(value: number): string {
  return value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

/** Suma de un campo numérico sobre un array de proyectos */
export function sumField(projects: BimProject[], key: keyof BimProject): number {
  return projects.reduce((acc, p) => acc + (p[key] as number), 0);
}
