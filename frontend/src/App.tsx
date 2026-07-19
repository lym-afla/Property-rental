import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from '@/context/SessionProvider'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/pages/HomePage'

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
            </Route>
          </Route>
          {/* /login and /register added in Tasks 8 & 9 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

export default App
