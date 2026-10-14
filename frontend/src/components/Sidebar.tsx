import type { ComponentType } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  Award,
  Users,
  BarChart3,
  ClipboardCheck,
  ShieldCheck,
  History,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Shield,
  X,
  FileStack,
  Sparkles,
} from 'lucide-react';
import type { NavItem } from '../lib/nav';
import { useAuth } from '../context/AuthContext';

interface SidebarProps {
  navItems: NavItem[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  isAdmin?: boolean;
}

const iconMap: Record<string, ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  PlusCircle,
  Award,
  Users,
  BarChart3,
  ClipboardCheck,
  ShieldCheck,
  History,
  User,
  FileStack,
  Sparkles,
};

export default function Sidebar({
  navItems,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  isAdmin = false,
}: SidebarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-[#0b1329] text-slate-300 border-r border-[#1e293b] transition-all duration-300 ease-in-out ${
          collapsed ? 'w-20' : 'w-64'
        } ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Header / Brand */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-[#1e293b]">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400 flex-shrink-0">
              <Shield className="w-5 h-5 text-teal-400" />
            </div>
            {!collapsed && (
              <div className="overflow-hidden whitespace-nowrap">
                <span className="font-bold text-white tracking-tight text-base block">
                  CertiVerify
                </span>
                <span className="text-[10px] text-teal-400 font-medium uppercase tracking-wider block">
                  {isAdmin ? 'Admin Console' : 'Portal'}
                </span>
              </div>
            )}
          </div>
          {/* Mobile close button */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden text-slate-400 hover:text-white p-1 rounded-md"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1.5">
          {!collapsed && (
            <p className="px-3 text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-2">
              Menu
            </p>
          )}
          {navItems.map(item => {
            const Icon = iconMap[item.icon] || Award;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.exact}
                onClick={onCloseMobile}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-teal-500/15 text-teal-400 border border-teal-500/30 font-semibold'
                      : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                  } ${collapsed ? 'justify-center' : ''}`
                }
              >
                <Icon className={`w-5 h-5 flex-shrink-0`} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
          })}
        </div>

        {/* User Card & Logout */}
        <div className="p-3 border-t border-[#1e293b] space-y-2">
          {!collapsed && user && (
            <div className="px-3 py-2 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-teal-600/30 text-teal-300 border border-teal-500/30 flex items-center justify-center font-bold text-xs uppercase flex-shrink-0">
                {user.name.charAt(0) || user.username?.charAt(0) || 'U'}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-white truncate">
                  {user.name || user.username}
                </p>
                <p className="text-[10px] text-slate-400 truncate">
                  {user.email}
                </p>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={handleLogout}
            title={collapsed ? 'Logout' : undefined}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-rose-400 hover:bg-rose-950/30 hover:text-rose-300 transition ${
              collapsed ? 'justify-center' : ''
            }`}
          >
            <LogOut className="w-5 h-5 flex-shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>

          {/* Desktop collapse toggle */}
          <div className="hidden lg:flex justify-end pt-1">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
