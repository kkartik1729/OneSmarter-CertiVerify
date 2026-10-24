import type { AdminUser } from '../types';
import { EP } from './endpoints';
import { http } from './http';
import { asList } from './mappers';

export const adminUsersService = {
  list: async (params?: { search?: string; role?: string }): Promise<AdminUser[]> => {
    let url = EP.adminUsers;
    const q = new URLSearchParams();
    if (params?.search) q.append('search', params.search);
    if (params?.role) q.append('role', params.role);
    const qs = q.toString();
    if (qs) url += `?${qs}`;
    const data = await http<unknown>('GET', url);
    return asList(data).map(mapAdminUser);
  },

  get: async (id: string | number): Promise<AdminUser> => {
    return mapAdminUser(await http<unknown>('GET', EP.adminUser(id)));
  },
};

function mapAdminUser(value: unknown): AdminUser {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Unexpected server response for user.');
  }
  const r = value as Record<string, unknown>;
  if (typeof r.id !== 'number' && typeof r.id !== 'string') {
    throw new Error('Unexpected server response: user ID is invalid.');
  }
  return {
    id: r.id,
    username: typeof r.username === 'string' ? r.username : '',
    email: typeof r.email === 'string' ? r.email : '',
    first_name: typeof r.first_name === 'string' ? r.first_name : '',
    last_name: typeof r.last_name === 'string' ? r.last_name : '',
    role: String(r.role ?? 'USER').toUpperCase() === 'ADMIN' ? 'ADMIN' : 'USER',
    date_joined: typeof r.date_joined === 'string' ? r.date_joined : '',
    mfa_enabled: r.mfa_enabled === true,
    email_verified: r.email_verified === true,
    phone: typeof r.phone === 'string' ? r.phone : undefined,
    organization: typeof r.organization === 'string' ? r.organization : undefined,
  };
}
