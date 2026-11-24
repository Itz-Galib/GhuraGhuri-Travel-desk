import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import { formatBdt } from '../tours/HomePage'

interface TourPkg {
  id: string
  title: string
  slug: string
  destination: string
  duration_days: number
  base_price: number
  status: string
}

interface Departure {
  id: string
  start_date: string
  end_date: string
  price: number
  capacity: number
  seats_booked: number
  status: string
}

interface Page<T> {
  items: T[]
}

export function OperatorToursPanel() {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [destination, setDestination] = useState('')
  const [summary, setSummary] = useState('')
  const [description, setDescription] = useState('')
  const [durationDays, setDurationDays] = useState(2)
  const [basePriceBdt, setBasePriceBdt] = useState(5000)
  const [policy, setPolicy] = useState('Free cancellation 7 days prior to departure.')
  const [selectedPkgId, setSelectedPkgId] = useState<string | null>(null)
  const [depStart, setDepStart] = useState('')
  const [depEnd, setDepEnd] = useState('')
  const [depCap, setDepCap] = useState(20)
  const [error, setError] = useState<string | null>(null)

  const toursQuery = useQuery({
    queryKey: ['operator-tours'],
    queryFn: () => apiRequest<Page<TourPkg>>(`${API_PREFIX}/operator/tours`),
  })

  const depsQuery = useQuery({
    queryKey: ['operator-departures', selectedPkgId],
    enabled: Boolean(selectedPkgId),
    queryFn: () =>
      apiRequest<Departure[]>(`${API_PREFIX}/operator/tours/${selectedPkgId}/departures`),
  })

  async function createTour(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiRequest(`${API_PREFIX}/operator/tours`, {
        method: 'POST',
        body: jsonBody({
          title,
          destination,
          summary,
          description,
          duration_days: durationDays,
          base_price: basePriceBdt * 100,
          advance_percent: 30,
          cancellation_policy: policy,
        }),
      })
      setTitle('')
      setDestination('')
      setSummary('')
      setDescription('')
      await queryClient.invalidateQueries({ queryKey: ['operator-tours'] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create tour.')
    }
  }

  async function publishTour(id: string) {
    setError(null)
    try {
      await apiRequest(`${API_PREFIX}/operator/tours/${id}/publish`, { method: 'POST' })
      await queryClient.invalidateQueries({ queryKey: ['operator-tours'] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publish failed.')
    }
  }

  async function addDeparture(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedPkgId) return
    setError(null)
    try {
      const pkg = toursQuery.data?.items.find((p) => p.id === selectedPkgId)
      await apiRequest(`${API_PREFIX}/operator/tours/${selectedPkgId}/departures`, {
        method: 'POST',
        body: jsonBody({
          start_date: depStart,
          end_date: depEnd,
          price: pkg?.base_price ?? basePriceBdt * 100,
          capacity: depCap,
        }),
      })
      setDepStart('')
      setDepEnd('')
      await queryClient.invalidateQueries({ queryKey: ['operator-departures', selectedPkgId] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to add departure.')
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <form
          onSubmit={createTour}
          className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5"
        >
          <h2 className="text-lg font-bold">New tour package</h2>
          <input
            type="text"
            required
            placeholder="Title (e.g. Sajek Valley 3D2N)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              type="text"
              required
              placeholder="Destination"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="number"
              min={1}
              required
              value={durationDays}
              onChange={(e) => setDurationDays(Number(e.target.value))}
              placeholder="Days"
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="number"
              min={0}
              required
              value={basePriceBdt}
              onChange={(e) => setBasePriceBdt(Number(e.target.value))}
              placeholder="Price (BDT)"
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <input
            type="text"
            required
            minLength={5}
            placeholder="Short summary"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <textarea
            required
            minLength={10}
            rows={3}
            placeholder="Full description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            type="text"
            required
            value={policy}
            onChange={(e) => setPolicy(e.target.value)}
            placeholder="Cancellation policy"
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Create draft package
          </button>
        </form>

        <div className="space-y-3">
          <h2 className="text-lg font-bold">Your packages</h2>
          {toursQuery.data?.items.map((pkg) => (
            <div
              key={pkg.id}
              className="rounded-2xl border border-slate-200 bg-white p-4 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedPkgId(pkg.id)}
                  className="text-left font-bold text-slate-900 hover:text-brand-700"
                >
                  {pkg.title}
                </button>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium">
                  {pkg.status}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {pkg.destination} · {pkg.duration_days}D · {formatBdt(pkg.base_price)}
              </p>
              <div className="flex gap-2">
                {pkg.status === 'DRAFT' && (
                  <button
                    type="button"
                    onClick={() => void publishTour(pkg.id)}
                    className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-700"
                  >
                    Publish
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setSelectedPkgId(pkg.id)}
                  className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Manage departures
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedPkgId && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
          <h3 className="text-lg font-bold">Departures</h3>
          <form onSubmit={addDeparture} className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-slate-600">Start date</label>
              <input
                type="date"
                required
                value={depStart}
                onChange={(e) => setDepStart(e.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600">End date</label>
              <input
                type="date"
                required
                value={depEnd}
                onChange={(e) => setDepEnd(e.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600">Capacity</label>
              <input
                type="number"
                min={1}
                required
                value={depCap}
                onChange={(e) => setDepCap(Number(e.target.value))}
                className="w-24 rounded-xl border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Add departure
            </button>
          </form>

          <div className="space-y-2">
            {depsQuery.data?.map((d) => (
              <div
                key={d.id}
                className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-2 text-sm"
              >
                <span>
                  {d.start_date} → {d.end_date}
                </span>
                <span>
                  {d.seats_booked}/{d.capacity} booked · {d.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
