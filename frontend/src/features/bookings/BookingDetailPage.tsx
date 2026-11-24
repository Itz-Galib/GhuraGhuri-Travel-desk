import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import { formatBdt } from '../tours/HomePage'

interface BookingDetail {
  id: string
  reference: string
  seats: number
  total_amount: number
  advance_required: number
  status: string
  expires_at: string | null
  contact_name: string
  contact_phone: string
  travellers: Array<{ id: string; full_name: string }>
  events: Array<{
    id: string
    from_status: string | null
    to_status: string
    note: string | null
    created_at: string
  }>
  payments: Array<{
    id: string
    provider: string
    amount: number
    provider_txn_id: string | null
    status: string
    note: string | null
  }>
}

export function BookingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [provider, setProvider] = useState<'BKASH' | 'NAGAD' | 'ROCKET' | 'CASH'>('BKASH')
  const [amountBdt, setAmountBdt] = useState('')
  const [senderNumber, setSenderNumber] = useState('+8801')
  const [txnId, setTxnId] = useState('')
  const [cancelReason, setCancelReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const query = useQuery({
    queryKey: ['booking-detail', id],
    enabled: Boolean(id),
    queryFn: () => apiRequest<BookingDetail>(`${API_PREFIX}/bookings/${id}`),
  })

  if (query.isLoading) {
    return <p className="py-10 text-center text-sm text-slate-500">Loading booking...</p>
  }
  if (!query.data) {
    return <p className="py-10 text-center text-sm text-slate-500">Booking not found.</p>
  }

  const b = query.data

  async function submitPayment(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const amountPoisha = amountBdt ? Math.round(Number(amountBdt) * 100) : b.advance_required
      await apiRequest(`${API_PREFIX}/bookings/${b.id}/payments`, {
        method: 'POST',
        body: jsonBody({
          provider,
          amount: amountPoisha,
          sender_number: senderNumber,
          provider_txn_id: provider === 'CASH' ? null : txnId,
        }),
      })
      setTxnId('')
      await queryClient.invalidateQueries({ queryKey: ['booking-detail', id] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Payment submission failed.')
    } finally {
      setBusy(false)
    }
  }

  async function requestCancel(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await apiRequest(`${API_PREFIX}/bookings/${b.id}/cancel-request`, {
        method: 'POST',
        body: jsonBody({ reason: cancelReason || 'Customer requested cancellation' }),
      })
      setCancelReason('')
      await queryClient.invalidateQueries({ queryKey: ['booking-detail', id] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Cancellation failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Booking reference
          </p>
          <h1 className="text-2xl font-bold text-slate-900">{b.reference}</h1>
          <p className="mt-1 text-sm text-slate-600">
            {b.seats} seat(s) · Total {formatBdt(b.total_amount)} · Advance required{' '}
            {formatBdt(b.advance_required)}
          </p>
        </div>
        <span className="rounded-full bg-brand-50 px-3 py-1.5 text-sm font-semibold text-brand-800">
          {b.status}
        </span>
      </header>

      {error && (
        <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {(b.status === 'PENDING_PAYMENT' || b.status === 'AWAITING_VERIFICATION') && (
        <form
          onSubmit={submitPayment}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6"
        >
          <h2 className="text-lg font-bold">Submit advance payment</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as 'BKASH' | 'NAGAD' | 'ROCKET' | 'CASH')}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="BKASH">bKash</option>
              <option value="NAGAD">Nagad</option>
              <option value="ROCKET">Rocket</option>
              <option value="CASH">Cash at office</option>
            </select>
            <input
              type="number"
              min={1}
              placeholder={`Amount BDT (default ${Math.round(b.advance_required / 100)})`}
              value={amountBdt}
              onChange={(e) => setAmountBdt(e.target.value)}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="tel"
              placeholder="Sender phone (+8801...)"
              value={senderNumber}
              onChange={(e) => setSenderNumber(e.target.value)}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            {provider !== 'CASH' && (
              <input
                type="text"
                required
                placeholder="Transaction ID (TrxID)"
                value={txnId}
                onChange={(e) => setTxnId(e.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            )}
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Submit payment
          </button>
        </form>
      )}

      {b.payments.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-2">
          <h2 className="text-lg font-bold">Payments</h2>
          {b.payments.map((p) => (
            <div
              key={p.id}
              className="flex flex-wrap items-center justify-between rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
            >
              <span>
                {p.provider} · {formatBdt(p.amount)}{' '}
                {p.provider_txn_id && `(${p.provider_txn_id})`}
              </span>
              <span className="font-semibold">{p.status}</span>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3">
        <h2 className="text-lg font-bold">Status timeline</h2>
        <ol className="space-y-2 border-l-2 border-brand-200 pl-4">
          {b.events.map((ev) => (
            <li key={ev.id} className="text-sm">
              <span className="font-semibold text-slate-900">{ev.to_status}</span>
              {ev.note && <span className="text-slate-600"> — {ev.note}</span>}
            </li>
          ))}
        </ol>
      </div>

      {(b.status === 'PENDING_PAYMENT' || b.status === 'CONFIRMED') && (
        <form
          onSubmit={requestCancel}
          className="flex flex-wrap gap-3 rounded-2xl border border-slate-200 bg-white p-6"
        >
          <input
            type="text"
            required
            placeholder="Reason for cancellation"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
          >
            Request cancellation
          </button>
        </form>
      )}
    </section>
  )
}
