import { Outlet } from 'react-router-dom';
import { Toaster } from '../lib/ui';

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans">
      <Outlet />
      <Toaster />
    </div>
  );
}
