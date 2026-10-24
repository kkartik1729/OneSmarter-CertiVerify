import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { homeFor, PATHS } from '../lib/paths';
import type { Role } from '../types';
import LoadingScreen from './LoadingScreen';

interface RoleBasedRouteProps {
  allowedRoles: Role[];
}

export default function RoleBasedRoute({ allowedRoles }: RoleBasedRouteProps) {
  const { user, loading, bootError, retryRestore } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingScreen />;

  if (bootError) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50 dark:bg-slate-950">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-md w-full text-center space-y-4 shadow-lg">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Cannot connect to server</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">{bootError}</p>
          <button
            type="button"
            onClick={retryRestore}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to={PATHS.login} replace state={{ from: location }} />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={homeFor(user.role)} replace />;
  }

  return <Outlet />;
}
