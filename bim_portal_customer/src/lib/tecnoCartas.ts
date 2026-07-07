import { getOdooBaseUrl } from '@/lib/odoo';

export interface TecnoCarta {
  id: number;
  titulo: string;
  texto: string;
}

export interface TecnoCartaCategoria {
  id: number;
  name: string;
  children: TecnoCartaCategoria[];
  cartas: TecnoCarta[];
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function fetchTecnoCartas(): Promise<TecnoCartaCategoria[]> {
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/tecno_cartas`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? (data.categories as TecnoCartaCategoria[]) : [];
}

/** Recorre el árbol y devuelve todas las cartas con referencia a su categoría */
export function flattenCartas(
  categories: TecnoCartaCategoria[],
): (TecnoCarta & { categoryName: string })[] {
  const result: (TecnoCarta & { categoryName: string })[] = [];
  function walk(cats: TecnoCartaCategoria[]) {
    for (const cat of cats) {
      for (const carta of cat.cartas) {
        result.push({ ...carta, categoryName: cat.name });
      }
      walk(cat.children);
    }
  }
  walk(categories);
  return result;
}
