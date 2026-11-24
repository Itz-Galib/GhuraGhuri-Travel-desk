import { useQuery, useQueryClient } from '@tanstack/react-query'
import { API_PREFIX, ApiError, apiRequest } from '../../lib/api/client'
import { OperatorBookingsPanel } from './OperatorBookingsPanel'
import { OperatorOnboarding, type OperatorProfile } from './OperatorOnboarding'
import { OperatorToursPanel } from './OperatorToursPanel'

export function OperatorArea() {
  const queryClient = useQueryClient()

  const profileQuery = useQuery({
    queryKey: ['operator-profile'],
    retry: false,
    queryFn: async (): Promise<OperatorProfile | null> => {
      try {
        return await apiRequest<OperatorProfile>(`${API_PREFIX}/operator/profile`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          return null
        }
        throw err
      }
    },
  })

  if (profileQuery.isLoading) {
    return <p className="py-8 text-center text-sm text-slate-500">Loading operator portal...</p>
  }

  const operator = profileQuery.data ?? null

  if (!operator || operator.verification_status !== 'APPROVED') {
    return (
      <OperatorOnboarding
        operator={operator}
        onUpdated={() => void queryClient.invalidateQueries({ queryKey: ['operator-profile'] })}
      />
    )
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">
            Operator portal · Verified
          </p>
          <h1 className="mt-1 text-3xl font-bold">{operator.display_name}</h1>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Packages', value: '0', hint: 'Draft or published' },
          { label: 'Upcoming departures', value: '0', hint: 'Next 30 days' },
          { label: 'Pending verifications', value: '0', hint: 'Payments to review' },
        ].map((card) => (
          <article key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-600">{card.label}</p>
            <p className="mt-2 text-3xl font-bold">{card.value}</p>
            <p className="mt-1 text-xs text-slate-500">{card.hint}</p>
          </article>
        ))}
      </div>
      <OperatorToursPanel />
      <OperatorBookingsPanel />
    </section>
  )
}
