import { Outlet, useLocation } from 'react-router-dom';
import { Toaster } from '../lib/ui';
import ErrorBoundary from './ErrorBoundary';

function RouteContent() {
  const location = useLocation();
  return <ErrorBoundary key={location.pathname}><Outlet /></ErrorBoundary>;
}

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans">
      <RouteContent />
      <Toaster />
    </div>
  );
}
