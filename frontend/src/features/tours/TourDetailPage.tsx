import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import { useAuth } from '../auth/AuthContext'
import { formatBdt, type OfferDto } from './HomePage'

interface DepartureDto {
  id: string
  start_date: string
  end_date: string
  price: number
  effective_price: number | null
  capacity: number
  seats_booked: number
  seats_left: number
  status: string
}

interface TourDetailResponse {
  package: {
    id: string
    title: string
    slug: string
    destination: string
    summary: string
    description: string
    itinerary: Array<{ day?: number; title?: string; details?: string }>
    inclusions: string[]
    exclusions: string[]
    duration_days: number
    base_price: number
    advance_percent: number
    cancellation_policy: string
  }
  operator_name: string
  operator_verified: boolean
  departures: DepartureDto[]
  active_offers: OfferDto[]
}

export function TourDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [selectedDepId, setSelectedDepId] = useState<string>('')
  const [seats, setSeats] = useState(1)
  const [contactName, setContactName] = useState(user?.full_name ?? '')
  const [contactPhone, setContactPhone] = useState(user?.phone ?? '+8801')
  const [travellerName, setTravellerName] = useState(user?.full_name ?? '')
  const [bookingError, setBookingError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const query = useQuery({
    queryKey: ['public-tour', slug],
    enabled: Boolean(slug),
    queryFn: () =>
      apiRequest<TourDetailResponse>(`${API_PREFIX}/tours/${slug}`, { skipAuth: true }),
  })

  if (query.isLoading) {
    return <p className="py-10 text-center text-sm text-slate-500">Loading tour details...</p>
  }
  if (query.isError || !query.data) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
        <h1 className="text-xl font-bold">Tour not found</h1>
        <Link to="/" className="mt-3 inline-block text-sm font-semibold text-brand-700 underline">
          Back to tours
        </Link>
      </div>
    )
  }

  const { package: pkg, operator_name, departures, active_offers } = query.data
  const activeDep = departures.find((d) => d.id === selectedDepId) ?? departures[0]

  async function handleBook(e: React.FormEvent) {
    e.preventDefault()
    if (!user) {
      navigate('/login', { state: { from: `/tours/${slug}` } })
      return
    }
    if (!activeDep) return
    setBookingError(null)
    setSubmitting(true)
    try {
      const created = await apiRequest<{ id: string }>(`${API_PREFIX}/bookings`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: jsonBody({
          departure_id: activeDep.id,
          seats,
          contact_name: contactName || user.full_name,
          contact_phone: contactPhone || user.phone,
          travellers: Array.from({ length: seats }, (_, idx) => ({
            full_name: idx === 0 ? travellerName || user.full_name : `Traveller ${idx + 1}`,
          })),
        }),
      })
      navigate(`/bookings/${created.id}`)
    } catch (err) {
      setBookingError(err instanceof ApiError ? err.message : 'Could not create booking.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <article className="grid gap-8 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <header className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
              {pkg.destination} · {pkg.duration_days} Days
            </span>
            <span className="text-xs font-medium text-emerald-700">
              ✓ Verified Operator: {operator_name}
            </span>
            {active_offers[0] && (
              <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                {active_offers[0].title}
              </span>
            )}
          </div>
          <h1 className="mt-3 text-3xl font-bold text-slate-900">{pkg.title}</h1>
          <p className="mt-2 text-slate-600">{pkg.summary}</p>
          <p className="mt-4 whitespace-pre-line text-sm leading-relaxed text-slate-700">
            {pkg.description}
          </p>
        </header>

        {pkg.itinerary.length > 0 && (
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-bold">Itinerary</h2>
            <ol className="mt-4 space-y-3">
              {pkg.itinerary.map((item, idx) => (
                <li key={idx} className="rounded-xl bg-slate-50 p-3 text-sm">
                  <strong className="text-brand-800">
                    Day {item.day ?? idx + 1}: {item.title}
                  </strong>
                  {item.details && <p className="mt-1 text-slate-600">{item.details}</p>}
                </li>
              ))}
            </ol>
          </section>
        )}

        <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-6 sm:grid-cols-2">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-emerald-700">
              Inclusions
            </h2>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
              {pkg.inclusions.map((inc, i) => (
                <li key={i}>{inc}</li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-rose-700">Exclusions</h2>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
              {pkg.exclusions.map((exc, i) => (
                <li key={i}>{exc}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">
            Cancellation policy
          </h2>
          <p className="mt-2 text-sm text-slate-600">{pkg.cancellation_policy}</p>
        </section>
      </div>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold">Book a departure</h2>
          {departures.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">
              No upcoming departures are currently open for booking.
            </p>
          ) : (
            <form onSubmit={handleBook} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">Select date</label>
                <select
                  value={activeDep?.id ?? ''}
                  onChange={(e) => setSelectedDepId(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                >
                  {departures.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.start_date} → {d.end_date} ({d.seats_left} left ·{' '}
                      {formatBdt(d.effective_price ?? d.price)})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700">Seats</label>
                <input
                  type="number"
                  min={1}
                  max={activeDep?.seats_left ?? 1}
                  value={seats}
                  onChange={(e) => setSeats(Math.max(1, Number(e.target.value)))}
                  className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                />
              </div>

              {user && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      Contact name
                    </label>
                    <input
                      type="text"
                      required
                      value={contactName}
                      onChange={(e) => setContactName(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      Contact phone (+8801...)
                    </label>
                    <input
                      type="tel"
                      required
                      value={contactPhone}
                      onChange={(e) => setContactPhone(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      Lead traveller name
                    </label>
                    <input
                      type="text"
                      required
                      value={travellerName}
                      onChange={(e) => setTravellerName(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                </>
              )}

              {activeDep && (
                <div className="rounded-xl bg-slate-50 p-3 text-sm">
                  <div className="flex justify-between">
                    <span>Total ({seats} seats)</span>
                    <strong>{formatBdt((activeDep.effective_price ?? activeDep.price) * seats)}</strong>
                  </div>
                  <div className="mt-1 flex justify-between text-xs text-slate-600">
                    <span>Advance required ({pkg.advance_percent}%)</span>
                    <span>
                      {formatBdt(
                        Math.round(
                          ((activeDep.effective_price ?? activeDep.price) *
                            seats *
                            pkg.advance_percent) /
                            100,
                        ),
                      )}
                    </span>
                  </div>
                </div>
              )}

              {bookingError && (
                <div role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700">
                  {bookingError}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting || !activeDep || activeDep.seats_left < 1}
                className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {user
                  ? submitting
                    ? 'Reserving seats...'
                    : 'Reserve seats'
                  : 'Sign in to book'}
              </button>
            </form>
          )}
        </div>
      </aside>
    </article>
  )
}
