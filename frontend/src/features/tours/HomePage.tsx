import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { API_PREFIX, apiRequest } from '../../lib/api/client'

export interface OfferDto {
  id: string
  package_id: string
  title: string
  discount_type: 'PERCENT' | 'FLAT'
  discount_value: number
}

export interface PublicTourSummary {
  id: string
  title: string
  slug: string
  destination: string
  summary: string
  duration_days: number
  base_price: number
  discounted_price: number
  operator_name: string
  operator_verified: boolean
  active_offer: OfferDto | null
}

interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

interface DepartureSearchItem {
  departure: {
    id: string
    start_date: string
    end_date: string
    seats_left: number
  }
  package_title: string
  package_slug: string
  destination: string
  duration_days: number
  operator_name: string
  discounted_price: number
}

export function formatBdt(poisha: number): string {
  return `৳${Math.round(poisha / 100).toLocaleString('en-BD')}`
}

export function HomePage() {
  const [q, setQ] = useState('')
  const [destination, setDestination] = useState('')
  const [dateSearch, setDateSearch] = useState('')
  const [sort, setSort] = useState('newest')

  const toursQuery = useQuery({
    queryKey: ['public-tours', q, destination, sort],
    enabled: !dateSearch,
    queryFn: () => {
      const params = new URLSearchParams()
      if (q.trim()) params.set('q', q.trim())
      if (destination.trim()) params.set('destination', destination.trim())
      if (sort) params.set('sort', sort)
      return apiRequest<Page<PublicTourSummary>>(`${API_PREFIX}/tours?${params.toString()}`, {
        skipAuth: true,
      })
    },
  })

  const departuresQuery = useQuery({
    queryKey: ['public-departures', dateSearch, destination],
    enabled: Boolean(dateSearch),
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('date', dateSearch)
      if (destination.trim()) params.set('destination', destination.trim())
      return apiRequest<Page<DepartureSearchItem>>(
        `${API_PREFIX}/departures?${params.toString()}`,
        { skipAuth: true },
      )
    },
  })

  return (
    <section className="space-y-8">
      <header className="rounded-3xl bg-gradient-to-br from-brand-700 to-brand-900 px-6 py-10 text-white sm:px-10">
        <p className="text-xs font-semibold uppercase tracking-widest text-brand-100">
          Verified Bangladesh Tour Operators
        </p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
          Book dated departures with confidence
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-brand-100 sm:text-base">
          Explore Sajek Valley, Sylhet tea gardens, Cox&apos;s Bazar, and the Sundarbans from
          admin-verified operators.
        </p>

        <div className="mt-6 grid gap-3 rounded-2xl bg-white p-3 text-slate-900 shadow-lg sm:grid-cols-4">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search tours..."
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
          />
          <input
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="Destination (e.g. Sajek)"
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
          />
          <input
            type="date"
            value={dateSearch}
            onChange={(e) => setDateSearch(e.target.value)}
            aria-label="Departure date"
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            disabled={Boolean(dateSearch)}
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none disabled:opacity-50"
          >
            <option value="newest">Newest</option>
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
          </select>
        </div>
      </header>

      {dateSearch ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Departures on {dateSearch}</h2>
            <button
              type="button"
              onClick={() => setDateSearch('')}
              className="text-sm font-semibold text-brand-700 hover:underline"
            >
              Clear date filter
            </button>
          </div>
          {departuresQuery.isLoading ? (
            <p className="text-sm text-slate-500">Searching departures...</p>
          ) : departuresQuery.data?.items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              No open departures found on {dateSearch}.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {departuresQuery.data?.items.map((item) => (
                <Link
                  key={item.departure.id}
                  to={`/tours/${item.package_slug}`}
                  className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-brand-400 hover:shadow-sm"
                >
                  <div>
                    <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700">
                      {item.destination} · {item.duration_days}D
                    </span>
                    <h3 className="mt-2 text-lg font-bold text-slate-900">{item.package_title}</h3>
                    <p className="mt-1 text-xs text-slate-500">by {item.operator_name}</p>
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
                    <span className="text-lg font-bold text-brand-700">
                      {formatBdt(item.discounted_price)}
                    </span>
                    <span className="text-xs font-medium text-emerald-700">
                      {item.departure.seats_left} seats left
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Published tour packages</h2>
          {toursQuery.isLoading ? (
            <p className="text-sm text-slate-500">Loading tours...</p>
          ) : toursQuery.data?.items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              No published tours match your filters yet.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {toursQuery.data?.items.map((tour) => (
                <Link
                  key={tour.id}
                  to={`/tours/${tour.slug}`}
                  className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-brand-400 hover:shadow-sm"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700">
                        {tour.destination} · {tour.duration_days}D
                      </span>
                      {tour.active_offer && (
                        <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                          {tour.active_offer.title}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-2 text-lg font-bold text-slate-900">{tour.title}</h3>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-600">{tour.summary}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {tour.operator_name} {tour.operator_verified && '✓ Verified'}
                    </p>
                  </div>
                  <div className="mt-4 flex items-baseline gap-2 border-t border-slate-100 pt-3">
                    <span className="text-lg font-bold text-brand-700">
                      {formatBdt(tour.discounted_price)}
                    </span>
                    {tour.discounted_price < tour.base_price && (
                      <span className="text-sm text-slate-400 line-through">
                        {formatBdt(tour.base_price)}
                      </span>
                    )}
                    <span className="ml-auto text-xs text-slate-500">per seat</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
