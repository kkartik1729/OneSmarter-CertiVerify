import type { DashboardStats } from '../types';
import { EP } from './endpoints';
import { http } from './http';

export const dashboardService = {
  get: async (): Promise<DashboardStats> => {
    return http<DashboardStats>('GET', EP.dashboard);
  },
};
