import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import { formatBdt } from '../tours/HomePage'

interface OperatorBooking {
  id: string
  reference: string
  contact_name: string
  contact_phone: string
  source: string
  seats: number
  total_amount: number
  advance_required: number
  status: string
}

interface Page<T> {
  items: T[]
}

export function OperatorBookingsPanel() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['operator-bookings', statusFilter],
    queryFn: () =>
      apiRequest<Page<OperatorBooking>>(
        `${API_PREFIX}/operator/bookings${statusFilter ? `?status=${statusFilter}` : ''}`,
      ),
  })

  async function actionBooking(id: string, action: 'confirm' | 'reject') {
    setError(null)
    try {
      await apiRequest(`${API_PREFIX}/operator/bookings/${id}/${action}`, {
        method: 'POST',
        body: action === 'reject' ? jsonBody({ reason: 'Rejected by operator' }) : undefined,
      })
      await queryClient.invalidateQueries({ queryKey: ['operator-bookings'] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action failed.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Booking queue</h2>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm"
        >
          <option value="">All statuses</option>
          <option value="PENDING_PAYMENT">Pending payment</option>
          <option value="AWAITING_VERIFICATION">Awaiting verification</option>
          <option value="CONFIRMED">Confirmed</option>
          <option value="CANCELLATION_REQUESTED">Cancellation requested</option>
        </select>
      </div>

      {error && (
        <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-2">
        {query.data?.items.map((b) => (
          <div
            key={b.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4"
          >
            <div>
              <p className="font-bold text-slate-900">
                {b.reference} · {b.contact_name}
              </p>
              <p className="text-xs text-slate-500">
                {b.contact_phone} · {b.seats} seat(s) · {formatBdt(b.total_amount)} · {b.source}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold">
                {b.status}
              </span>
              {(b.status === 'PENDING_PAYMENT' || b.status === 'AWAITING_VERIFICATION') && (
                <>
                  <button
                    type="button"
                    onClick={() => void actionBooking(b.id, 'confirm')}
                    className="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={() => void actionBooking(b.id, 'reject')}
                    className="rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    Reject
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
