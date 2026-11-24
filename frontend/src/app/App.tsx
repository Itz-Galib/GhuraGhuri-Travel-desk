import { Link, Route, Routes } from 'react-router-dom'
import { AdminArea } from '../features/admin/AdminArea'
import { LoginPage } from '../features/auth/LoginPage'
import { RegisterPage } from '../features/auth/RegisterPage'
import { RequireAuth } from '../features/auth/RequireAuth'
import { BookingDetailPage } from '../features/bookings/BookingDetailPage'
import { MyBookingsPage } from '../features/bookings/MyBookingsPage'
import { NotificationsPage } from '../features/bookings/NotificationsPage'
import { OperatorArea } from '../features/operator/OperatorArea'
import { HomePage } from '../features/tours/HomePage'
import { TourDetailPage } from '../features/tours/TourDetailPage'
import { NotFoundPage } from './NotFoundPage'
import { AppLayout } from './AppLayout'

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="tours/:slug" element={<TourDetailPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route
          path="bookings"
          element={
            <RequireAuth>
              <MyBookingsPage />
            </RequireAuth>
          }
        />
        <Route
          path="bookings/:id"
          element={
            <RequireAuth>
              <BookingDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="notifications"
          element={
            <RequireAuth>
              <NotificationsPage />
            </RequireAuth>
          }
        />
        <Route
          path="operator/*"
          element={
            <RequireAuth roles={['OPERATOR', 'CUSTOMER']}>
              <OperatorArea />
            </RequireAuth>
          }
        />
        <Route
          path="admin/*"
          element={
            <RequireAuth roles={['ADMIN']}>
              <AdminArea />
            </RequireAuth>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold text-brand-900">
      <span
        aria-hidden="true"
        className="grid size-9 place-items-center rounded-xl bg-brand-600 text-lg text-white"
      >
        ঘ
      </span>
      <span>GhuraGhuri</span>
    </Link>
  )
}
