import { getOdooBaseUrl } from '@/lib/odoo';

export type AusenciaTipo = 'vacaciones' | 'permiso' | 'otros';
export type AusenciaState = 'draft' | 'submitted' | 'approved' | 'rejected';

export interface Ausencia {
  id: number;
  name: string;
  tipo: AusenciaTipo;
  tipo_label: string;
  state: AusenciaState;
  state_label: string;
  date_create: string;
  date_from: string;
  date_to: string;
  descripcion: string;
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchAusencias(): Promise<Ausencia[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/ausencias`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.ausencias as Ausencia[]) : [];
}

export async function createAusencia(body: {
  tipo: AusenciaTipo;
  date_from: string;
  date_to: string;
  descripcion?: string;
}): Promise<Ausencia | null> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/ausencias`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
    keepalive: true,
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? (data.ausencia as Ausencia) : null;
}
