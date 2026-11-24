import type { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth, type UserRole } from './AuthContext'

interface RequireAuthProps extends PropsWithChildren {
  roles?: UserRole[]
}

export function RequireAuth({ roles, children }: RequireAuthProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="py-12 text-center text-sm text-slate-500">Checking your session...</div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (roles && !roles.includes(user.role)) {
    return (
      <section className="mx-auto max-w-md rounded-2xl border border-amber-200 bg-amber-50 p-6 text-center">
        <h1 className="text-lg font-bold text-amber-900">Access denied</h1>
        <p className="mt-1 text-sm text-amber-800">
          Your account role ({user.role}) does not have permission to view this area.
        </p>
      </section>
    )
  }

  return <>{children}</>
}
