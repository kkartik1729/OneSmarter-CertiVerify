import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import AppLayout from './components/AppLayout';
import RoleBasedRoute from './components/RoleBasedRoute';
import AdminLayout from './components/AdminLayout';
import UserLayout from './components/UserLayout';

import LoadingScreen from './components/LoadingScreen';

const Home = lazy(() => import('./pages/Home'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'));
const NotFound = lazy(() => import('./pages/NotFound'));

// Admin Pages
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const ReviewCertificates = lazy(() => import('./pages/admin/ReviewCertificates'));
const ManageUsers = lazy(() => import('./pages/admin/ManageUsers'));
const Analytics = lazy(() => import('./pages/admin/Analytics'));
const VerificationLogs = lazy(() => import('./pages/admin/VerificationLogs'));
const AdminProfile = lazy(() => import('./pages/admin/AdminProfile'));
const GenerateCertificates = lazy(() => import('./pages/admin/GenerateCertificates'));
const SingleCertificate = lazy(() => import('./pages/admin/SingleCertificate'));
const GenerationHistory = lazy(() => import('./pages/admin/GenerationHistory'));

// User Pages
const UserDashboard = lazy(() => import('./pages/user/UserDashboard'));
const VerifyCertificate = lazy(() => import('./pages/user/VerifyCertificate'));
const MyCertificates = lazy(() => import('./pages/user/MyCertificates'));
const VerificationHistory = lazy(() => import('./pages/user/VerificationHistory'));
const UserProfile = lazy(() => import('./pages/user/UserProfile'));

const MfaRecovery = lazy(() => import('./pages/MfaRecovery'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const PublicVerify = lazy(() => import('./pages/PublicVerify'));
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
          <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route element={<AppLayout />}>
              {/* Public Routes */}
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/verify" element={<VerifyCertificate />} />
              {/* Public certificate verification routes — no auth required */}
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
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
