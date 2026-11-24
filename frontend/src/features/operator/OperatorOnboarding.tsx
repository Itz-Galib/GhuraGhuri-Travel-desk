import { useState } from 'react'
import { API_PREFIX, ApiError, apiRequest, jsonBody } from '../../lib/api/client'
import { useAuth } from '../auth/AuthContext'

export interface OperatorProfile {
  id: string
  type: 'INDIVIDUAL' | 'GROUP'
  display_name: string
  contact_phone: string
  facebook_url: string | null
  payout_methods: Array<{ provider: string; number: string }>
  verification_status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'SUSPENDED'
  verification_note: string | null
}

interface Props {
  operator: OperatorProfile | null
  onUpdated: () => void
}

export function OperatorOnboarding({ operator, onUpdated }: Props) {
  const { refreshMe } = useAuth()
  const [type, setType] = useState<'INDIVIDUAL' | 'GROUP'>('GROUP')
  const [displayName, setDisplayName] = useState('')
  const [contactPhone, setContactPhone] = useState('+8801')
  const [facebookUrl, setFacebookUrl] = useState('')
  const [payoutProvider, setPayoutProvider] = useState<'BKASH' | 'NAGAD' | 'ROCKET'>('BKASH')
  const [payoutNumber, setPayoutNumber] = useState('')

  const [personName, setPersonName] = useState('')
  const [docType, setDocType] = useState<'NID_FRONT' | 'NID_BACK' | 'SELFIE' | 'AUTHORIZATION_NOTE'>('NID_FRONT')
  const [nidNumber, setNidNumber] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleCreateProfile(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await apiRequest<OperatorProfile>(`${API_PREFIX}/operator/profile`, {
        method: 'POST',
        body: jsonBody({
          type,
          display_name: displayName,
          contact_phone: contactPhone,
          facebook_url: facebookUrl || null,
          payout_methods: [{ provider: payoutProvider, number: payoutNumber }],
        }),
      })
      await refreshMe()
      onUpdated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create operator profile.')
    } finally {
      setBusy(false)
    }
  }

  async function handleUploadDoc(e: React.FormEvent) {
    e.preventDefault()
    if (!file) {
      setError('Please select a file to upload.')
      return
    }
    setError(null)
    setMessage(null)
    setBusy(true)
    try {
      const form = new FormData()
      form.append('person_name', personName)
      form.append('doc_type', docType)
      if (docType === 'NID_FRONT' && nidNumber) {
        form.append('nid_number', nidNumber)
      }
      form.append('file', file)
      await apiRequest(`${API_PREFIX}/operator/documents`, {
        method: 'POST',
        body: form,
      })
      setMessage(`Uploaded ${docType} successfully.`)
      setFile(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmitVerification() {
    setError(null)
    setBusy(true)
    try {
      await apiRequest(`${API_PREFIX}/operator/submit`, { method: 'POST' })
      await refreshMe()
      onUpdated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Submission failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">
          Operator onboarding
        </p>
        <h1 className="mt-1 text-2xl font-bold">Verify your tour operator account</h1>
        <p className="mt-1 text-sm text-slate-600">
          Verified operators can publish tour packages and receive bookings.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {message}
        </div>
      )}

      {!operator ? (
        <form
          onSubmit={handleCreateProfile}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6"
        >
          <h2 className="text-lg font-semibold">Step 1: Organisation details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700">Operator type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as 'INDIVIDUAL' | 'GROUP')}
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="GROUP">Tour Group / Agency</option>
                <option value="INDIVIDUAL">Individual Guide</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Display name</label>
              <input
                type="text"
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Sajek Explorers BD"
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Contact phone (+8801...)
              </label>
              <input
                type="tel"
                required
                pattern="^\+8801[3-9]\d{8}$"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Facebook Page / Group URL
              </label>
              <input
                type="url"
                value={facebookUrl}
                onChange={(e) => setFacebookUrl(e.target.value)}
                placeholder="https://facebook.com/groups/..."
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700">Payout provider</label>
              <select
                value={payoutProvider}
                onChange={(e) => setPayoutProvider(e.target.value as 'BKASH' | 'NAGAD' | 'ROCKET')}
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="BKASH">bKash</option>
                <option value="NAGAD">Nagad</option>
                <option value="ROCKET">Rocket</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Payout number</label>
              <input
                type="text"
                required
                value={payoutNumber}
                onChange={(e) => setPayoutNumber(e.target.value)}
                placeholder="017XXXXXXXX"
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? 'Saving...' : 'Save profile & continue'}
          </button>
        </form>
      ) : (
        <div className="space-y-6">
          {operator.verification_status === 'REJECTED' && operator.verification_note && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <strong>Rejected:</strong> {operator.verification_note}
            </div>
          )}

          {operator.verification_status === 'PENDING' ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-lg font-semibold text-amber-900">Application under review</h2>
              <p className="mt-1 text-sm text-amber-800">
                An admin is reviewing your NID and payout details for{' '}
                <strong>{operator.display_name}</strong>. You can draft packages once approved.
              </p>
            </div>
          ) : (
            <form
              onSubmit={handleUploadDoc}
              className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6"
            >
              <h2 className="text-lg font-semibold">
                Step 2: Upload verification documents ({operator.display_name})
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Document holder name
                  </label>
                  <input
                    type="text"
                    required
                    value={personName}
                    onChange={(e) => setPersonName(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Document type</label>
                  <select
                    value={docType}
                    onChange={(e) =>
                      setDocType(
                        e.target.value as
                          | 'NID_FRONT'
                          | 'NID_BACK'
                          | 'SELFIE'
                          | 'AUTHORIZATION_NOTE',
                      )
                    }
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  >
                    <option value="NID_FRONT">NID Front</option>
                    <option value="NID_BACK">NID Back</option>
                    <option value="SELFIE">Selfie with NID</option>
                    <option value="AUTHORIZATION_NOTE">Group Authorisation Note</option>
                  </select>
                </div>
              </div>

              {docType === 'NID_FRONT' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    NID number (10, 13, or 17 digits — encrypted at rest)
                  </label>
                  <input
                    type="text"
                    required
                    value={nidNumber}
                    onChange={(e) => setNidNumber(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700">
                  File (JPEG, PNG, WEBP, or PDF, max 5 MB)
                </label>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="mt-1 block w-full text-sm text-slate-600"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Upload document
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void handleSubmitVerification()}
                  className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                >
                  Submit for admin review
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </section>
  )
}
