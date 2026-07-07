import { getOdooBaseUrl } from '@/lib/odoo';

export interface AvanceLine {
  id: number;
  name: string;
  image: string; // base64
}

export interface Avance {
  id: number;
  name: string;
  fecha: string;
  user: string;
  project_id: number;
  project_name: string;
  descripcion: string;
  image_count: number;
  lines?: AvanceLine[];
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchAvances(): Promise<Avance[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/cliente/avances`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.avances as Avance[]) : [];
}

export async function fetchAvance(id: number): Promise<Avance | null> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/cliente/avances/${id}`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? (data.avance as Avance) : null;
}

// ── Mensajes / Chatter ──────────────────────────────────────────────────────

export interface AvanceMessage {
  id: number;
  author: string;
  date: string;
  body: string;
}

export async function fetchAvanceMessages(id: number): Promise<AvanceMessage[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/cliente/avances/${id}/messages`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.messages as AvanceMessage[]) : [];
}

export async function postAvanceComment(id: number, body: string): Promise<AvanceMessage | null> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/cliente/avances/${id}/messages`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ body }),
    keepalive: true,
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? (data.message as AvanceMessage) : null;
}
