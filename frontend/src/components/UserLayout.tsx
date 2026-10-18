import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNavbar from './TopNavbar';
import { USER_NAV } from '../lib/nav';

const titleMap: Record<string, string> = {
  '/user/dashboard': 'User Overview',
  '/user/dashboard/verify': 'Verify Certificate',
  '/user/dashboard/certificates': 'My Certificates',
  '/user/dashboard/history': 'Verification History',
  '/user/dashboard/profile': 'Profile & Security',
};

export default function UserLayout() {
  const [collapsed, setCollapsed] = useState(true);
  const [hoverExpanded, setHoverExpanded] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const currentTitle = titleMap[location.pathname] || 'Certificate Portal';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex">
      <Sidebar
        navItems={USER_NAV}
        collapsed={collapsed}
        hoverExpanded={hoverExpanded}
        onHoverExpandedChange={setHoverExpanded}
        onToggleCollapse={() => { setCollapsed(prev => !prev); setHoverExpanded(false); }}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        isAdmin={false}
      />

      <div
        className={`flex-1 flex flex-col transition-all duration-300 min-w-0 ${
          collapsed && !hoverExpanded ? 'lg:pl-20' : 'lg:pl-64'
        }`}
      >
        <TopNavbar
          onOpenMobileSidebar={() => setMobileOpen(true)}
          title={currentTitle}
          isAdmin={false}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
