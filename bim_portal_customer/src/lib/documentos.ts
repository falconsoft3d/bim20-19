import { getOdooBaseUrl } from '@/lib/odoo';

export interface BimDocumento {
  id: number;
  name: string;
  desc: string;
  date: string;
  project_id: number | false;
  project_name: string;
  categoria_id: number | false;
  categoria_name: string;
  file_name: string;
  download_url: string;
  has_file: boolean;
  share_url: string;
  type: string;
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchDocumentos(): Promise<BimDocumento[]> {
  try {
    const res = await fetch(`${getOdooBaseUrl()}/bim_portal/cliente/documentos`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.success ? (data.documentos as BimDocumento[]) : [];
  } catch {
    return [];
  }
}
