/**
 * Servicio de autenticación contra Odoo (bim_portal_customer_odoo).
 * Todos los endpoints apuntan a /bim_portal/auth/*
 */

import { getOdooBaseUrl, setOdooBaseUrl } from '@/lib/odoo';

export interface PartnerProfile {
  id: number;
  name: string;
  email: string;
  phone: string;
  login: string;
  company: string;
  responsible: string;
  is_customer: boolean;
  is_employee: boolean;
  is_admin: boolean;
  is_tecno_cartas: boolean;
  is_proveedor: boolean;
}

export interface AuthResponse {
  success: boolean;
  token?: string;
  partner?: PartnerProfile;
  error?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function getAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ── Token en localStorage ─────────────────────────────────────────────────────

const TOKEN_KEY = 'bim_portal_token';
const PARTNER_KEY = 'bim_portal_partner';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredPartner(): PartnerProfile | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(PARTNER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PartnerProfile;
  } catch {
    return null;
  }
}

function storeSession(token: string, partner: PartnerProfile): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(PARTNER_KEY, JSON.stringify(partner));
}

function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(PARTNER_KEY);
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function login(loginStr: string, password: string, odooUrl?: string): Promise<AuthResponse> {
  if (odooUrl) setOdooBaseUrl(odooUrl);
  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login: loginStr.trim().toLowerCase(), password }),
  });

  const data: AuthResponse = await res.json();

  if (data.success && data.token && data.partner) {
    storeSession(data.token, data.partner);
  }

  return data;
}

export async function logout(): Promise<void> {
  const token = getStoredToken();
  if (token) {
    await fetch(`${getOdooBaseUrl()}/bim_portal/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
      keepalive: true,
    }).catch(() => null); // No bloquear aunque falle la red
  }
  clearSession();
}

export async function getMe(): Promise<PartnerProfile | null> {
  const token = getStoredToken();
  if (!token) return null;

  const res = await fetch(`${getOdooBaseUrl()}/bim_portal/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    clearSession();
    return null;
  }

  const data = await res.json();
  if (data.success && data.partner) {
    return data.partner as PartnerProfile;
  }
  clearSession();
  return null;
}

export function isAuthenticated(): boolean {
  return !!getStoredToken();
}

/** Llama a /me, actualiza localStorage y devuelve el partner fresco */
export async function refreshPartner(): Promise<PartnerProfile | null> {
  const partner = await getMe();
  if (partner) {
    const token = getStoredToken();
    if (token) storeSession(token, partner);
  }
  return partner;
}
