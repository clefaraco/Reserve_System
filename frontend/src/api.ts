import { createClient } from '@supabase/supabase-js'

export const TENANT = import.meta.env.VITE_TENANT_ID ?? '10000000-0000-4000-8000-000000000001'
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
// Publishable key only. NEVER place a service-role key or encryption key in a VITE variable.
export const auth = url && key ? createClient(url, key, {
  auth: { persistSession: false, autoRefreshToken: true, detectSessionInUrl: true },
}) : null

export async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`/v1/${TENANT}${path}`, { ...options, headers, cache: 'no-store' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Revisa los datos e inténtalo nuevamente.')
  }
  return response.json()
}

export type Service = { service_id: string; service_name: string; resource_id: string; public_name: string;
  branch: string; specialty: string; timezone: string; duration_minutes: number; buffer_minutes: number }
export type Document = { id: string; kind: 'terms' | 'sensitive_data' | 'whatsapp'; version: string; body: string }
export type Catalog = { tenant: string; services: Service[]; documents: Document[]; account_available: boolean;
  cancel_cutoff_minutes: number; reschedule_cutoff_minutes: number }
export type Appointment = { id: string; patient_id: string; starts_at: string; ends_at: string; status: string;
  version: number; service_name: string; public_name: string; timezone: string }
