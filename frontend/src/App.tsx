import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from '@/context/SessionProvider'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes — outside ProtectedRoute so unauthenticated users
              can reach them (resolves the Task 7 redirect-loop). */}
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
            </Route>
          </Route>
          {/* /register added in Task 9 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

export default App
