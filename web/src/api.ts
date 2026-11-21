export type Lang = 'ru' | 'kk'

export interface Reason { code: string; text: string }
export interface CheckResult {
  verdict: 'scam' | 'suspicious' | 'safe'
  score: number
  scheme: string | null
  scheme_name: string | null
  reasons: Reason[]
  advice: string
  source: 'rules' | 'llm' | 'cache'
  text: string | null
}
export interface Question { id: number; text: string }
export interface TransferView {
  id: string
  status: 'completed' | 'warning' | 'questions' | 'held' | 'awaiting_family' | 'cancelled' | 'escalated'
  level: number
  score: number
  amount: number
  account: string
  holder: string
  title: string | null
  message: string | null
  questions: Question[]
  reasons: string[]
  guardian_name: string | null
  balance: number
}
export interface FamilyRequest {
  id: string
  ward_name: string
  ward_title: string
  ward_phone: string
  amount: number
  account: string
  holder: string
  headline: string
  explanation: string
  advice: string
  timeline: { ts: number; text: string }[]
  expires_in: number
}
export interface Notice { id: string; ts: number; kind: 'family_request' | 'shield_disable' | 'info'; title: string; body: string; ref: string | null }
export type Shield =
  | { role: 'ward'; guardian_name: string; guardian_title: string; limit: number; active: boolean; disable_at: number | null }
  | { role: 'guardian'; wards: { ward_id: string; name: string; title: string; limit: number; active: boolean; disable_at: number | null }[] }
  | { role: 'none' }
export interface Sms { id: string; sender: string; text: string; sample_id: string | null; ts: number }
export interface Snapshot {
  epoch: number
  client: { id: string; name: string; short: string; lang: Lang; balance: number; avatar: string; guardian: string | null; phone: string }
  call: { number: string; label: string; answered: boolean; since: number } | null
  sms: Sms[]
  prefill: { account: string; amount: number; note?: string } | null
  nav: { screen: string; seq: number } | null
  transfers: TransferView[]
  family_requests: FamilyRequest[]
  notices: Notice[]
  shield: Shield
  history: { title: string; amount: number; ts: number }[]
}
export interface CallVerify { status: 'bank' | 'not_bank' | 'no_call'; title: string; message: string; number: string | null; number_complaints: number }
export interface Sample { id: string; sender: string; text: string; label: Record<Lang, string>; image: string; based_on: string | null }
export interface SchemeCard { id: string; date: string; title: string; how: string; sign: string; source: string }
export interface VictimHelp { steps: string[]; statement: { title: string; body: string }; source: string }
export interface StageEvent { seq: number; ts: number; kind: string; client_id: string | null; text: string; step: string | null; stopped: boolean }
export interface Stage { steps: string[]; stopped: number; saved: number; events: StageEvent[] }

// Presenter key for a public deployment: open /stage?key=... once, it is remembered on this device.
const KEY_STORAGE = 'qaqpan.directorKey'
export function captureDirectorKey() {
  try {
    const k = new URLSearchParams(window.location.search).get('key')
    if (k) localStorage.setItem(KEY_STORAGE, k)
  } catch { /* storage may be unavailable */ }
}
function directorKey(): string | null {
  try { return localStorage.getItem(KEY_STORAGE) } catch { return null }
}

async function req<T>(url: string, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  let r: Response
  try {
    r = await fetch(url, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Нет связи с сервером')
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Проверьте введённые данные')
  }
  return r.json() as Promise<T>
}

export const api = {
  phone: (id: string) => req<Snapshot>(`/api/phone/${id}`),
  setLang: (id: string, lang: Lang) => req<{ lang: Lang }>(`/api/phone/${id}/lang/${lang}`, {}),
  answerCall: (id: string) => req(`/api/phone/${id}/call/answer`, {}),
  endCall: (id: string) => req(`/api/phone/${id}/call/end`, {}),
  check: (body: { client_id?: string; text?: string; image_b64?: string; media_type?: string; sample_id?: string; lang: Lang }) =>
    req<CheckResult>('/api/messages/check', body),
  verifyCall: (client_id: string) => req<CallVerify>('/api/calls/verify', { client_id }),
  transfer: (body: { client_id: string; account: string; amount: number; context: { pasted: boolean; app_switches: number } }) =>
    req<TransferView>('/api/transfers', body),
  answers: (id: string, answers: boolean[]) => req<TransferView>(`/api/transfers/${id}/answers`, { answers }),
  cancel: (id: string) => req<TransferView>(`/api/transfers/${id}/cancel`, {}),
  proceed: (id: string) => req<TransferView>(`/api/transfers/${id}/proceed`, {}),
  family: (rid: string, client_id: string, approve: boolean) =>
    req<{ status: string }>(`/api/family/requests/${rid}/decision`, { client_id, approve }),
  shieldDisable: (wardId: string) => req<{ disable_at: number }>(`/api/family/${wardId}/disable`, {}),
  shieldKeep: (wardId: string) => req<{ disable_at: null }>(`/api/family/${wardId}/keep`, {}),
  noticeSeen: (id: string, nid: string) => req(`/api/phone/${id}/notices/${nid}/seen`, {}),
  complain: (client_id: string, transfer_id: string) => req<{ message: string }>('/api/complaints', { client_id, transfer_id }),
  victim: (client_id: string, lang: Lang, transfer_id?: string, story?: string) =>
    req<VictimHelp>('/api/victim/help', { client_id, lang, transfer_id, story: story || null }),
  schemes: (lang: Lang) => req<SchemeCard[]>(`/api/schemes?lang=${lang}`),
  samples: () => req<Sample[]>('/api/samples'),
  stage: () => req<Stage>('/api/stage'),
  assistant: (client_id: string, lang: Lang, messages: { role: 'user' | 'assistant'; content: string }[]) =>
    req<{ reply: string; source: string }>('/api/assistant', { client_id, lang, messages }),
  director: (action: string) => {
    const k = directorKey()
    return req(`/api/director/${action}`, {}, k ? { 'X-Director-Key': k } : {})
  },
  nativeCall: (id: string, on_call: boolean) => req(`/api/phone/${id}/native-call`, { on_call }),
}

export const money = (n: number) => `${Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ')} ₸`
