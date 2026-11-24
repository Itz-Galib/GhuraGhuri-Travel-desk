import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import type { OperatorProfile } from '../operator/OperatorOnboarding'

interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

interface VerificationDoc {
  id: string
  person_name: string
  doc_type: string
  nid_last4: string | null
  created_at: string
}

interface OperatorDetail {
  operator: OperatorProfile
  documents: VerificationDoc[]
}

export function AdminOperatorsPanel() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('PENDING')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [signedUrl, setSignedUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const listQuery = useQuery({
    queryKey: ['admin-operators', statusFilter],
    queryFn: () =>
      apiRequest<Page<OperatorProfile>>(
        `${API_PREFIX}/admin/operators${statusFilter ? `?verification_status=${statusFilter}` : ''}`,
      ),
  })

  const detailQuery = useQuery({
    queryKey: ['admin-operator-detail', selectedId],
    enabled: Boolean(selectedId),
    queryFn: () => apiRequest<OperatorDetail>(`${API_PREFIX}/admin/operators/${selectedId}`),
  })

  async function viewDocUrl(operatorId: string, docId: string) {
    setError(null)
    try {
      const res = await apiRequest<{ url: string }>(
        `${API_PREFIX}/admin/operators/${operatorId}/documents/${docId}/url`,
      )
      setSignedUrl(res.url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to issue signed URL.')
    }
  }

  async function decide(operatorId: string, action: 'approve' | 'reject' | 'suspend') {
    setError(null)
    try {
      await apiRequest(`${API_PREFIX}/admin/operators/${operatorId}/${action}`, {
        method: 'POST',
        body: jsonBody({ reason: reason || `Admin ${action}` }),
      })
      setReason('')
      setSignedUrl(null)
      await queryClient.invalidateQueries({ queryKey: ['admin-operators'] })
      await queryClient.invalidateQueries({ queryKey: ['admin-operator-detail', operatorId] })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action failed.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Operator applications</h2>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setSelectedId(null)
          }}
          className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm"
        >
          <option value="PENDING">Pending</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="SUSPENDED">Suspended</option>
          <option value="">All</option>
        </select>
      </div>

      {error && (
        <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          {listQuery.data?.items.map((op) => (
            <button
              key={op.id}
              type="button"
              onClick={() => {
                setSelectedId(op.id)
                setSignedUrl(null)
              }}
              className={`w-full rounded-xl border p-4 text-left transition ${
                selectedId === op.id
                  ? 'border-brand-600 bg-brand-50/40'
                  : 'border-slate-200 bg-white hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-900">{op.display_name}</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                  {op.verification_status}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {op.type} · {op.contact_phone}
              </p>
            </button>
          ))}
          {listQuery.data?.items.length === 0 && (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
              No operators in this status.
            </p>
          )}
        </div>

        {detailQuery.data && (
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div>
              <h3 className="text-lg font-bold">{detailQuery.data.operator.display_name}</h3>
              <p className="text-sm text-slate-600">
                {detailQuery.data.operator.contact_phone}
                {detailQuery.data.operator.facebook_url && (
                  <>
                    {' '}
                    ·{' '}
                    <a
                      href={detailQuery.data.operator.facebook_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-brand-700 underline"
                    >
                      Facebook
                    </a>
                  </>
                )}
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">Verification documents</h4>
              {detailQuery.data.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 text-sm"
                >
                  <div>
                    <span className="font-medium">{doc.doc_type}</span> · {doc.person_name}
                    {doc.nid_last4 && (
                      <span className="ml-2 text-xs text-slate-500">NID ****{doc.nid_last4}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void viewDocUrl(detailQuery.data.operator.id, doc.id)}
                    className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200"
                  >
                    60s Signed URL
                  </button>
                </div>
              ))}
              {signedUrl && (
                <div className="rounded-xl bg-slate-50 p-3 text-xs">
                  <span className="font-semibold">Audit-logged signed URL:</span>{' '}
                  <a href={signedUrl} target="_blank" rel="noreferrer" className="text-brand-700 underline break-all">
                    Open document
                  </a>
                </div>
              )}
            </div>

            <div className="space-y-2 border-t border-slate-100 pt-3">
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Decision reason (required for reject/suspend)"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void decide(detailQuery.data.operator.id, 'approve')}
                  className="rounded-xl bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700"
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => void decide(detailQuery.data.operator.id, 'reject')}
                  className="rounded-xl bg-amber-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-amber-700"
                >
                  Reject
                </button>
                <button
                  type="button"
                  onClick={() => void decide(detailQuery.data.operator.id, 'suspend')}
                  className="rounded-xl bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700"
                >
                  Suspend
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
