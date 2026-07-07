/**
 * Servicio de perfil de usuario para el Portal BIM.
 */
import { getStoredPartner, PartnerProfile } from './auth';

const ODOO_BASE_URL = process.env.NEXT_PUBLIC_ODOO_URL || 'http://localhost:8069';

function authHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('bim_portal_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface ProfileUpdatePayload {
  name?: string;
  email?: string;
  phone?: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface ProfileResponse {
  success: boolean;
  partner?: PartnerProfile;
  message?: string;
  error?: string;
}

export async function fetchProfile(): Promise<PartnerProfile | null> {
  try {
    const res = await fetch(`${ODOO_BASE_URL}/bim_portal/profile`, {
      headers: authHeaders(),
    });
    const data = await res.json();
    if (data.success && data.partner) {
      localStorage.setItem('bim_portal_partner', JSON.stringify(data.partner));
      return data.partner as PartnerProfile;
    }
    return null;
  } catch {
    // Offline: devolver lo que hay en localStorage
    return getStoredPartner();
  }
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<ProfileResponse> {
  const res = await fetch(`${ODOO_BASE_URL}/bim_portal/profile/update`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  const data: ProfileResponse = await res.json();
  if (data.success && data.partner) {
    localStorage.setItem('bim_portal_partner', JSON.stringify(data.partner));
  }
  return data;
}

export async function changePassword(payload: ChangePasswordPayload): Promise<ProfileResponse> {
  const res = await fetch(`${ODOO_BASE_URL}/bim_portal/profile/change_password`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return res.json();
}
