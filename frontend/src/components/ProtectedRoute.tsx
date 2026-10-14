import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { homeFor, PATHS } from '../lib/paths';
import type { Role } from '../types';
import LoadingScreen from './LoadingScreen';

/**
 * Route guard (navigation only; the backend still enforces permissions).
 *  - restoring session -> loading screen
 *  - not signed in      -> /login
 *  - wrong role         -> that user's own dashboard (no loop: their own dashboard always matches)
 */
export default function ProtectedRoute({ role }: { role: Role }) {
  const { user, loading, bootError, retryRestore } = useAuth();

  if (loading) return <LoadingScreen />;

  if (bootError) {
    return (
      <div className="ms"><div>
        <h2>Cannot reach the server</h2>
        <p className="mu" role="alert">{bootError}</p>
        <button className="btn" onClick={retryRestore}>Try again</button>
      </div></div>
    );
  }

  if (!user) return <Navigate to={PATHS.login} replace />;
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
