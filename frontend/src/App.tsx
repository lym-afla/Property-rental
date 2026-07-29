import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from '@/context/SessionProvider'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'

const HomePage = lazy(() => import('@/pages/HomePage').then(({ HomePage }) => ({ default: HomePage })))
const LoginPage = lazy(() => import('@/pages/LoginPage').then(({ LoginPage }) => ({ default: LoginPage })))
const RegisterPage = lazy(() => import('@/pages/RegisterPage').then(({ RegisterPage }) => ({ default: RegisterPage })))
const PropertiesPage = lazy(() => import('@/pages/PropertiesPage').then(({ PropertiesPage }) => ({ default: PropertiesPage })))
const PropertyDetailPage = lazy(() => import('@/pages/PropertyDetailPage').then(({ PropertyDetailPage }) => ({ default: PropertyDetailPage })))
const TenantsPage = lazy(() => import('@/pages/TenantsPage').then(({ TenantsPage }) => ({ default: TenantsPage })))
const TenantDetailPage = lazy(() => import('@/pages/TenantDetailPage').then(({ TenantDetailPage }) => ({ default: TenantDetailPage })))
const TransactionsPage = lazy(() => import('@/pages/TransactionsPage').then(({ TransactionsPage }) => ({ default: TransactionsPage })))
const FXPage = lazy(() => import('@/pages/FXPage').then(({ FXPage }) => ({ default: FXPage })))
const ProfilePage = lazy(() => import('@/pages/ProfilePage').then(({ ProfilePage }) => ({ default: ProfilePage })))

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading page">
      Loading page…
    </div>
  )
}

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
          {/* Public routes — outside ProtectedRoute so unauthenticated users
              can reach them (resolves the Task 7 redirect-loop). */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/properties" element={<PropertiesPage />} />
              <Route path="/properties/:id" element={<PropertyDetailPage />} />
              <Route path="/tenants" element={<TenantsPage />} />
              <Route path="/tenants/:id" element={<TenantDetailPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/fx" element={<FXPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </SessionProvider>
  )
}

export default App
