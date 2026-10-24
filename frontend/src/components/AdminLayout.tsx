import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNavbar from './TopNavbar';
import { ADMIN_NAV } from '../lib/nav';

const titleMap: Record<string, string> = {
  '/admin/dashboard': 'Admin Overview',
  '/admin/dashboard/generate': 'Generate Certificates in Bulk',
  '/admin/dashboard/generate-single': 'Generate Single Certificate',
  '/admin/dashboard/generation-history': 'Generation History & Batches',
  '/admin/dashboard/add': 'Add New Certificate',
  '/admin/dashboard/certificates': 'Manage Certificates',
  '/admin/dashboard/users': 'Registered Users',
  '/admin/dashboard/analytics': 'Analytics & Reporting',
  '/admin/dashboard/verifications': 'Verification Records',
  '/admin/dashboard/profile': 'Admin Profile & Security',
  '/admin/dashboard/set-password': 'Set Manual Password',
};

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(true);
  const [hoverExpanded, setHoverExpanded] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const currentTitle = titleMap[location.pathname] || 'Admin Console';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex">
      <Sidebar
        navItems={ADMIN_NAV}
        collapsed={collapsed}
        hoverExpanded={hoverExpanded}
        onHoverExpandedChange={setHoverExpanded}
        onToggleCollapse={() => { setCollapsed(prev => !prev); setHoverExpanded(false); }}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        isAdmin={true}
      />

      <div
        className={`flex-1 flex flex-col transition-all duration-300 min-w-0 ${
          collapsed && !hoverExpanded ? 'lg:pl-20' : 'lg:pl-64'
        }`}
      >
        <TopNavbar
          onOpenMobileSidebar={() => setMobileOpen(true)}
          title={currentTitle}
          isAdmin={true}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
