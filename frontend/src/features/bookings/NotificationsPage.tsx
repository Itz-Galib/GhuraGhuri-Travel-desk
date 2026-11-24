import { useQuery, useQueryClient } from '@tanstack/react-query'
import { API_PREFIX, apiRequest } from '../../lib/api/client'

interface NotificationDto {
  id: string
  booking_id: string | null
  channel: string
  title: string
  body: string
  read_at: string | null
  created_at: string
}

interface Page<T> {
  items: T[]
}

export function NotificationsPage() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['my-notifications'],
    queryFn: () => apiRequest<Page<NotificationDto>>(`${API_PREFIX}/notifications`),
  })

  async function markRead(id: string) {
    await apiRequest(`${API_PREFIX}/notifications/${id}/read`, { method: 'POST' })
    await queryClient.invalidateQueries({ queryKey: ['my-notifications'] })
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Notifications</h1>
        <p className="text-sm text-slate-600">Booking confirmations, updates, and alerts.</p>
      </header>

      {query.isLoading ? (
        <p className="text-sm text-slate-500">Loading notifications...</p>
      ) : query.data?.items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No notifications yet.
        </p>
      ) : (
        <div className="space-y-3">
          {query.data?.items.map((n) => (
            <article
              key={n.id}
              className={`rounded-2xl border p-4 ${
                n.read_at ? 'border-slate-200 bg-white' : 'border-brand-300 bg-brand-50/40'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-slate-900">{n.title}</h2>
                  <p className="mt-1 text-sm text-slate-600">{n.body}</p>
                </div>
                {!n.read_at && (
                  <button
                    type="button"
                    onClick={() => void markRead(n.id)}
                    className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
                  >
                    Mark read
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
