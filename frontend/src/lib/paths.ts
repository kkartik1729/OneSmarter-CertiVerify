import type { Role } from '../types';

/** Every frontend route that the auth code needs to know about. */
export const PATHS = {
  login: '/login',
  register: '/register',
  userHome: '/user/dashboard',
  adminHome: '/admin/dashboard',
} as const;

/** Dashboard that belongs to a role. */
export const homeFor = (role: Role): string => (role === 'admin' ? PATHS.adminHome : PATHS.userHome);
