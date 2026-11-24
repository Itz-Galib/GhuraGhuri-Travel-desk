import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import {
  API_PREFIX,
  apiRequest,
  jsonBody,
  refreshAccessToken,
  setAccessToken,
} from '../../lib/api/client'

export type UserRole = 'CUSTOMER' | 'OPERATOR' | 'ADMIN'

export interface UserProfile {
  id: string
  full_name: string
  email: string
  phone: string
  role: UserRole
  status: 'ACTIVE' | 'SUSPENDED'
  created_at: string
}

export interface OperatorMembership {
  operator_id: string
  display_name: string
  member_role: string
  verification_status: string
}

interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: UserProfile
}

interface MeResponse {
  user: UserProfile
  operator_memberships: OperatorMembership[]
}

export interface RegisterPayload {
  full_name: string
  email: string
  phone: string
  password: string
  consent: boolean
}

interface AuthContextValue {
  user: UserProfile | null
  memberships: OperatorMembership[]
  isLoading: boolean
  login: (identifier: string, password: string) => Promise<UserProfile>
  register: (payload: RegisterPayload) => Promise<UserProfile>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [memberships, setMemberships] = useState<OperatorMembership[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const refreshMe = useCallback(async () => {
    try {
      const me = await apiRequest<MeResponse>(`${API_PREFIX}/me`)
      setUser(me.user)
      setMemberships(me.operator_memberships)
    } catch {
      setUser(null)
      setMemberships([])
    }
  }, [])

  useEffect(() => {
    let active = true
    ;(async () => {
      const token = await refreshAccessToken()
      if (token && active) {
        await refreshMe()
      }
      if (active) setIsLoading(false)
    })()
    return () => {
      active = false
    }
  }, [refreshMe])

  const login = useCallback(
    async (identifier: string, password: string) => {
      const res = await apiRequest<AuthResponse>(`${API_PREFIX}/auth/login`, {
        method: 'POST',
        credentials: 'include',
        skipAuth: true,
        skipRefresh: true,
        body: jsonBody({ identifier, password }),
      })
      setAccessToken(res.access_token)
      setUser(res.user)
      await refreshMe()
      return res.user
    },
    [refreshMe],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const res = await apiRequest<AuthResponse>(`${API_PREFIX}/auth/register`, {
        method: 'POST',
        credentials: 'include',
        skipAuth: true,
        skipRefresh: true,
        body: jsonBody(payload),
      })
      setAccessToken(res.access_token)
      setUser(res.user)
      setMemberships([])
      return res.user
    },
    [],
  )

  const logout = useCallback(async () => {
    try {
      await apiRequest<void>(`${API_PREFIX}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        skipAuth: true,
        skipRefresh: true,
      })
    } finally {
      setAccessToken(null)
      setUser(null)
      setMemberships([])
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, memberships, isLoading, login, register, logout, refreshMe }),
    [user, memberships, isLoading, login, register, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return ctx
}
