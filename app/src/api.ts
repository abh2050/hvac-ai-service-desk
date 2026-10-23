import { fetchAuthSession } from 'aws-amplify/auth';
import { STATIC } from './mode';

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Every request carries the Cognito ID token; API Gateway validates it before the Lambda runs.
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (STATIC) {
    if (init.method && init.method !== 'GET') throw new ApiError(405, 'This is a recorded demo, so it cannot change anything.');
    const res = await fetch(`/snapshot${path}.json`);
    if (!res.ok) throw new ApiError(res.status, 'Not part of the recorded demo.');
    return res.json() as Promise<T>;
  }
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', authorization: token ?? '', ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

export type Me = { sub: string; role: 'manager' | 'technician'; technician_id: string | null };
