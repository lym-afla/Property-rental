import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from '@/context/SessionProvider'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { PropertiesPage } from '@/pages/PropertiesPage'
import { RegisterPage } from '@/pages/RegisterPage'

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes — outside ProtectedRoute so unauthenticated users
              can reach them (resolves the Task 7 redirect-loop). */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/properties" element={<PropertiesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

export default App
