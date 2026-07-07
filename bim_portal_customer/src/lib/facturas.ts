import { getOdooBaseUrl } from '@/lib/odoo';

export type FacturaState = 'submitted' | 'approved' | 'rejected';

export interface FacturaAdjunto {
  id: number;
  name: string;
  url: string;
}

export interface FacturaProveedor {
  id: number;
  name: string;
  proveedor_id: number;
  proveedor: string;
  project_id: number;
  project: string;
  importe: number;
  fecha: string;
  state: FacturaState;
  state_label: string;
  notas: string;
  adjuntos: FacturaAdjunto[];
}

export interface SelectOption {
  id: number;
  name: string;
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchFacturas(): Promise<FacturaProveedor[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/facturas`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.facturas as FacturaProveedor[]) : [];
}

export async function fetchProveedores(q = ''): Promise<SelectOption[]> {
  const params = q.trim().length >= 1 ? `?q=${encodeURIComponent(q.trim())}` : '';
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/facturas/proveedores${params}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.proveedores as SelectOption[]) : [];
}

export async function fetchProyectosFactura(): Promise<SelectOption[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/facturas/proyectos`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.proyectos as SelectOption[]) : [];
}

export async function createFactura(body: {
  proveedor_id: number;
  project_id: number;
  importe: number;
  fecha: string;
  notas?: string;
  adjunto_b64?: string;
  adjunto_nombre?: string;
}): Promise<{ factura: FacturaProveedor } | { error: string }> {
  try {
    const res = await fetch(`${getOdooBaseUrl()}/bim_portal/facturas`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      return { error: data.error || `Error ${res.status}` };
    }
    return { factura: data.factura as FacturaProveedor };
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'Error de red' };
  }
}

/** Convierte un File del navegador a string base64 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = (reader.result as string).split(',')[1];
      resolve(result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export async function accionFactura(
  id: number,
  accion: 'approve' | 'reject',
): Promise<FacturaProveedor | null> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/facturas/${id}/accion`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ accion }),
    keepalive: true,
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? (data.factura as FacturaProveedor) : null;
}
