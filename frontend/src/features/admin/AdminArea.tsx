import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { API_PREFIX, apiRequest, getAccessToken, jsonBody } from '../../lib/api/client'
import { formatBdt } from '../tours/HomePage'
import { AdminOperatorsPanel } from './AdminOperatorsPanel'

type Tab = 'operators' | 'bookings' | 'audit'

interface AdminDashboard {
  pending_operators: number
  needs_attention: number
  revenue_booked: number
  bookings_by_status: Record<string, number>
}

interface AdminBooking {
  id: string
  reference: string
  contact_name: string
  contact_phone: string
  source: string
  seats: number
  total_amount: number
  status: string
  needs_attention: boolean
}

interface AuditEntry {
  id: string
  action: string
  entity_type: string
  entity_id: string | null
  created_at: string
}

interface Page<T> {
  items: T[]
}

export function AdminArea() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('operators')
  const [unavailMsg, setUnavailMsg] = useState<{ text: string; url: string } | null>(null)

  const dashQuery = useQuery({
    queryKey: ['admin-dashboard'],
    queryFn: () => apiRequest<AdminDashboard>(`${API_PREFIX}/admin/dashboard`),
  })

  const bookingsQuery = useQuery({
    queryKey: ['admin-bookings'],
    enabled: tab === 'bookings',
    queryFn: () => apiRequest<Page<AdminBooking>>(`${API_PREFIX}/admin/bookings`),
  })

  const auditQuery = useQuery({
    queryKey: ['admin-audit'],
    enabled: tab === 'audit',
    queryFn: () => apiRequest<Page<AuditEntry>>(`${API_PREFIX}/admin/audit-logs`),
  })

  async function notifyUnavailable(bookingId: string) {
    const res = await apiRequest<{ message_text: string; whatsapp_url: string }>(
      `${API_PREFIX}/admin/bookings/${bookingId}/notify-unavailable`,
      {
        method: 'POST',
        body: jsonBody({ reason: 'Package/departure unavailable' }),
      },
    )
    setUnavailMsg({ text: res.message_text, url: res.whatsapp_url })
    await queryClient.invalidateQueries({ queryKey: ['admin-bookings'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] })
  }

  async function downloadCsv() {
    const base = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
    const token = getAccessToken()
    const res = await fetch(`${base}${API_PREFIX}/admin/bookings?format=csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bookings.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const dash = dashQuery.data

  return (
    <section className="space-y-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">Admin panel</p>
        <h1 className="mt-1 text-3xl font-bold">Platform oversight</h1>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Operators pending', value: String(dash?.pending_operators ?? 0) },
          {
            label: 'Total bookings',
            value: String(
              Object.values(dash?.bookings_by_status ?? {}).reduce((a, b) => a + b, 0),
            ),
          },
          { label: 'Needs attention', value: String(dash?.needs_attention ?? 0) },
          { label: 'Revenue booked', value: formatBdt(dash?.revenue_booked ?? 0) },
        ].map((card) => (
          <article key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-600">{card.label}</p>
            <p className="mt-2 text-2xl font-bold">{card.value}</p>
          </article>
        ))}
      </div>

      <div className="flex gap-2 border-b border-slate-200 pb-2">
        {(['operators', 'bookings', 'audit'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold capitalize ${
              tab === t ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {t === 'audit' ? 'Audit logs' : t}
          </button>
        ))}
      </div>

      {tab === 'operators' && <AdminOperatorsPanel />}

      {tab === 'bookings' && (
        <div className="space-y-4">
          <div className="flex justify-between">
            <h2 className="text-lg font-semibold">All bookings</h2>
            <button
              type="button"
              onClick={() => void downloadCsv()}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold hover:bg-slate-50"
            >
              Export CSV
            </button>
          </div>
          {unavailMsg && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm">
              <p className="font-semibold text-amber-900">Copyable customer message:</p>
              <p className="mt-1 text-amber-800">{unavailMsg.text}</p>
              <a
                href={unavailMsg.url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block font-semibold text-brand-700 underline"
              >
                Open in WhatsApp
              </a>
            </div>
          )}
          <div className="space-y-2">
            {bookingsQuery.data?.items.map((b) => (
              <div
                key={b.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm"
              >
                <div>
                  <span className="font-bold">{b.reference}</span> · {b.contact_name} (
                  {b.contact_phone}) · {b.source} · {formatBdt(b.total_amount)}
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold">
                    {b.status}
                  </span>
                  {b.status !== 'CANCELLED_UNAVAILABLE' && b.status !== 'CANCELLED' && (
                    <button
                      type="button"
                      onClick={() => void notifyUnavailable(b.id)}
                      className="rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white"
                    >
                      Notify unavailable
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'audit' && (
        <div className="space-y-2">
          {auditQuery.data?.items.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm"
            >
              <span>
                <strong>{a.action}</strong> · {a.entity_type}
              </span>
              <span className="text-xs text-slate-500">
                {new Date(a.created_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
