export interface NavItem {
  path: string;
  label: string;
  icon: string;
  exact?: boolean;
}

export const ADMIN_NAV: NavItem[] = [
  { path: '/admin/dashboard', label: 'Overview', icon: 'LayoutDashboard', exact: true },
  { path: '/admin/dashboard/generate', label: 'Bulk Generation', icon: 'FileStack' },
  { path: '/admin/dashboard/generate-single', label: 'Manual Generation', icon: 'Sparkles' },
  { path: '/admin/dashboard/generation-history', label: 'Generation History', icon: 'History' },
  { path: '/admin/dashboard/certificates', label: 'Manage Certificates', icon: 'Award' },
  { path: '/admin/dashboard/users', label: 'Users Management', icon: 'Users' },
  { path: '/admin/dashboard/analytics', label: 'Analytics', icon: 'BarChart3' },
  { path: '/admin/dashboard/verifications', label: 'Verification Records', icon: 'ClipboardCheck' },
  { path: '/admin/dashboard/profile', label: 'Profile & Security', icon: 'ShieldCheck' },
];

export const USER_NAV: NavItem[] = [
  { path: '/user/dashboard', label: 'Overview', icon: 'LayoutDashboard', exact: true },
  { path: '/user/dashboard/verify', label: 'Verify Certificate', icon: 'ShieldCheck' },
  { path: '/user/dashboard/certificates', label: 'My Certificates', icon: 'Award' },
  { path: '/user/dashboard/history', label: 'Verification History', icon: 'History' },
  { path: '/user/dashboard/profile', label: 'Profile & Security', icon: 'User' },
];
