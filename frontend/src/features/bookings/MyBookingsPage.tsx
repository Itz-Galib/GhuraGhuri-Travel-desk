import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { API_PREFIX, apiRequest } from '../../lib/api/client'
import { formatBdt } from '../tours/HomePage'

interface BookingSummary {
  id: string
  reference: string
  seats: number
  total_amount: number
  advance_required: number
  status: string
  created_at: string
}

interface Page<T> {
  items: T[]
  total: number
}

export function MyBookingsPage() {
  const query = useQuery({
    queryKey: ['my-bookings'],
    queryFn: () => apiRequest<Page<BookingSummary>>(`${API_PREFIX}/bookings`),
  })

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">My bookings</h1>
        <p className="text-sm text-slate-600">Track payments, status timeline, and cancellations.</p>
      </header>

      {query.isLoading ? (
        <p className="text-sm text-slate-500">Loading bookings...</p>
      ) : query.data?.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          You have no bookings yet.{' '}
          <Link to="/" className="font-semibold text-brand-700 underline">
            Explore tours
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {query.data?.items.map((b) => (
            <Link
              key={b.id}
              to={`/bookings/${b.id}`}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-brand-400"
            >
              <div>
                <p className="font-bold text-slate-900">{b.reference}</p>
                <p className="text-xs text-slate-500">
                  {b.seats} seat(s) · Total {formatBdt(b.total_amount)} (Advance{' '}
                  {formatBdt(b.advance_required)})
                </p>
              </div>
              <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-800">
                {b.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
