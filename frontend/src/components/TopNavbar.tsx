import { Menu, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ThemeToggle } from '../lib/ui';

interface TopNavbarProps {
  onOpenMobileSidebar: () => void;
  title?: string;
  isAdmin?: boolean;
}

export default function TopNavbar({
  onOpenMobileSidebar,
  title = 'Dashboard',
  isAdmin = false,
}: TopNavbarProps) {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-30 h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-3 sm:px-6 flex items-center justify-between gap-2 sm:gap-4 shadow-sm">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="lg:hidden shrink-0 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="min-w-0 truncate text-base sm:text-lg font-bold text-slate-900 dark:text-white tracking-tight">
          {title}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {/* Role badge */}
        <span
          className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
            isAdmin
              ? 'bg-purple-100 text-purple-700 border border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800'
              : 'bg-teal-100 text-teal-700 border border-teal-200 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-800'
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          {isAdmin ? 'Administrator' : 'Standard User'}
        </span>

        {/* Theme toggle */}
        <ThemeToggle />

        {/* User avatar indicator */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-800">
          <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-slate-700 dark:text-slate-200 font-semibold text-xs uppercase">
            {user?.name?.charAt(0) || user?.username?.charAt(0) || 'U'}
          </div>
          <div className="hidden md:block text-left text-xs">
            <p className="font-semibold text-slate-800 dark:text-slate-100 truncate max-w-[120px]">
              {user?.name || user?.username}
            </p>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">
              {user?.role}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
