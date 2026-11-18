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
  from_name: string
  amount: number
  account: string
  holder: string
  reasons: string[]
  said_yes: boolean
  expires_in: number
}
export interface Sms { id: string; sender: string; text: string; sample_id: string | null; ts: number }
export interface Snapshot {
  epoch: number
  client: { id: string; name: string; short: string; lang: Lang; balance: number; avatar: string; guardian: string | null }
  call: { number: string; label: string; answered: boolean; since: number } | null
  sms: Sms[]
  prefill: { account: string; amount: number; note?: string } | null
  nav: { screen: string; seq: number } | null
  transfers: TransferView[]
  family_requests: FamilyRequest[]
}
export interface CallVerify { status: 'bank' | 'not_bank' | 'no_call'; title: string; message: string; number: string | null; number_complaints: number }
export interface Sample { id: string; sender: string; text: string; label: Record<Lang, string>; image: string; based_on: string | null }
export interface SchemeCard { id: string; date: string; title: string; how: string; sign: string; source: string }
export interface VictimHelp { steps: string[]; statement: { title: string; body: string }; source: string }
export interface StageEvent { seq: number; ts: number; kind: string; client_id: string | null; text: string; step: string | null; stopped: boolean }
export interface Stage { steps: string[]; stopped: number; events: StageEvent[] }

async function req<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Ошибка запроса')
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
  family: (rid: string, approve: boolean) => req<{ status: string }>(`/api/family/${rid}/decision`, { approve }),
  complain: (client_id: string, transfer_id: string) => req<{ message: string }>('/api/complaints', { client_id, transfer_id }),
  victim: (client_id: string, lang: Lang, transfer_id?: string, story?: string) =>
    req<VictimHelp>('/api/victim/help', { client_id, lang, transfer_id, story: story || null }),
  schemes: (lang: Lang) => req<SchemeCard[]>(`/api/schemes?lang=${lang}`),
  samples: () => req<Sample[]>('/api/samples'),
  stage: () => req<Stage>('/api/stage'),
  director: (action: string) => req(`/api/director/${action}`, {}),
  nativeCall: (id: string, on_call: boolean) => req(`/api/phone/${id}/native-call`, { on_call }),
}

export const money = (n: number) => `${Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ')} ₸`
