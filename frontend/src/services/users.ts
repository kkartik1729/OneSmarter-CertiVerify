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
    return asList(data).map(r => ({
      id: r.id as number | string,
      username: String(r.username ?? ''),
      email: String(r.email ?? ''),
      first_name: String(r.first_name ?? ''),
      last_name: String(r.last_name ?? ''),
      role: (String(r.role ?? 'USER').toUpperCase() === 'ADMIN' ? 'ADMIN' : 'USER') as 'ADMIN' | 'USER',
      date_joined: String(r.date_joined ?? ''),
      mfa_enabled: Boolean(r.mfa_enabled),
      phone: r.phone ? String(r.phone) : undefined,
      organization: r.organization ? String(r.organization) : undefined,
    }));
  },

  get: async (id: string | number): Promise<AdminUser> => {
    const r = await http<Record<string, unknown>>('GET', EP.adminUser(id));
    return {
      id: r.id as number | string,
      username: String(r.username ?? ''),
      email: String(r.email ?? ''),
      first_name: String(r.first_name ?? ''),
      last_name: String(r.last_name ?? ''),
      role: (String(r.role ?? 'USER').toUpperCase() === 'ADMIN' ? 'ADMIN' : 'USER') as 'ADMIN' | 'USER',
      date_joined: String(r.date_joined ?? ''),
      mfa_enabled: Boolean(r.mfa_enabled),
      phone: r.phone ? String(r.phone) : undefined,
      organization: r.organization ? String(r.organization) : undefined,
    };
  },
};
