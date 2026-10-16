import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import AppLayout from './components/AppLayout';
import RoleBasedRoute from './components/RoleBasedRoute';
import AdminLayout from './components/AdminLayout';
import UserLayout from './components/UserLayout';

import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import VerifyEmail from './pages/VerifyEmail';
import NotFound from './pages/NotFound';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import ReviewCertificates from './pages/admin/ReviewCertificates';
import ManageUsers from './pages/admin/ManageUsers';
import Analytics from './pages/admin/Analytics';
import VerificationLogs from './pages/admin/VerificationLogs';
import AdminProfile from './pages/admin/AdminProfile';
import GenerateCertificates from './pages/admin/GenerateCertificates';
import SingleCertificate from './pages/admin/SingleCertificate';
import GenerationHistory from './pages/admin/GenerationHistory';

// User Pages
import UserDashboard from './pages/user/UserDashboard';
import VerifyCertificate from './pages/user/VerifyCertificate';
import MyCertificates from './pages/user/MyCertificates';
import VerificationHistory from './pages/user/VerificationHistory';
import UserProfile from './pages/user/UserProfile';

import MfaRecovery from './pages/MfaRecovery';
import ForgotPassword from './pages/ForgotPassword';
import PublicVerify from './pages/PublicVerify';
import { useAuth } from './context/AuthContext';
import SetManualPassword from './components/SetManualPassword';

import ErrorBoundary from './components/ErrorBoundary';

// Role-aware root dashboard redirect
function DashboardRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'admin' ? '/admin/dashboard' : '/user/dashboard'} replace />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route element={<AppLayout />}>
              {/* Public Routes */}
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/verify" element={<VerifyCertificate />} />
              {/* Public LinkedIn credential URL routes — no auth required */}
              <Route path="/verify-certificate" element={<PublicVerify />} />
              <Route path="/verify-certificate/:certificateNumber" element={<PublicVerify />} />
              <Route path="/verify/:certificateNumber" element={<PublicVerify />} />
              <Route path="/mfa-recovery" element={<MfaRecovery />} />
              <Route path="/mfa-recovery/confirm" element={<MfaRecovery />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/forgot-password/verify" element={<ForgotPassword />} />
              <Route path="/forgot-password/reset" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ForgotPassword />} />
              <Route path="/reset-password/confirm" element={<ForgotPassword />} />

              {/* Role-neutral dashboard redirect */}
              <Route path="/dashboard" element={<DashboardRedirect />} />

              {/* Admin Dashboard Protected Routes */}
              <Route element={<RoleBasedRoute allowedRoles={['admin']} />}>
                <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
                <Route path="/admin/dashboard" element={<AdminLayout />}>
                  <Route index element={<AdminDashboard />} />
                  <Route path="generate" element={<GenerateCertificates />} />
                  <Route path="generate-single" element={<SingleCertificate />} />
                  <Route path="generation-history" element={<GenerationHistory />} />
                  <Route path="add" element={<Navigate to="/admin/dashboard/generate-single" replace />} />
                  <Route path="certificates" element={<ReviewCertificates />} />
                  <Route path="users" element={<ManageUsers />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="verifications" element={<VerificationLogs />} />
                  <Route path="profile" element={<AdminProfile />} />
                  <Route path="set-password" element={<div className="max-w-4xl mx-auto"><SetManualPassword /></div>} />
                </Route>
              </Route>

              {/* User Dashboard Protected Routes */}
              <Route element={<RoleBasedRoute allowedRoles={['user']} />}>
                <Route path="/user" element={<Navigate to="/user/dashboard" replace />} />
                <Route path="/user/dashboard" element={<UserLayout />}>
                  <Route index element={<UserDashboard />} />
                  <Route path="verify" element={<VerifyCertificate />} />
                  <Route path="certificates" element={<MyCertificates />} />
                  <Route path="history" element={<VerificationHistory />} />
                  <Route path="profile" element={<UserProfile />} />
                  <Route path="set-password" element={<div className="max-w-4xl mx-auto"><SetManualPassword /></div>} />
                </Route>
              </Route>

              {/* 404 Catch-All */}
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
