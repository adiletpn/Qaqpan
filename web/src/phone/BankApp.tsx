import { useCallback, useEffect, useRef, useState } from 'react'
import { api, money, type CallVerify, type Lang, type Snapshot, type TransferView } from '../api'
import { tr } from '../i18n'
import { Card, Icon } from '../ui'
import { CheckScreen, ResultScreen, SchemesScreen, TransferScreen, VictimScreen } from './screens'
import { CallPill, FamilySheet, IncomingCall, SmsBanner, VerifySheet } from './overlays'

export type Screen = 'home' | 'check' | 'transfer' | 'result' | 'victim' | 'schemes'

export default function BankApp({ clientId }: { clientId: string }) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [screen, setScreen] = useState<Screen>('home')
  const [transfer, setTransfer] = useState<TransferView | null>(null)
  const [checkSample, setCheckSample] = useState<string | null>(null)
  const [verify, setVerify] = useState<CallVerify | null>(null)
  const [dismissedSms, setDismissedSms] = useState<string | null>(null)
  const navSeq = useRef(0)

  const refresh = useCallback(async () => {
    try { setSnap(await api.phone(clientId)) } catch { /* server restarting: keep last snapshot */ }
  }, [clientId])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 900)
    return () => clearInterval(t)
  }, [refresh])

  // director-driven navigation (prefilled transfer, victim help); each nav fires once
  useEffect(() => {
    const nav = snap?.nav
    if (!nav || nav.seq <= navSeq.current) return
    navSeq.current = nav.seq
    if (nav.screen === 'transfer' || nav.screen === 'victim') setScreen(nav.screen)
  }, [snap?.nav])

  // a full reset on the server clears transfers: go back home
  const lastTransferCount = useRef(0)
  useEffect(() => {
    const n = snap?.transfers.length ?? 0
    if (n < lastTransferCount.current && screen !== 'home') { setScreen('home'); setTransfer(null); setVerify(null) }
    lastTransferCount.current = n
  }, [snap?.transfers.length, screen])

  if (!snap) return <div className="grid h-full place-items-center text-slate-400">…</div>
  const lang: Lang = snap.client.lang
  const liveTransfer = transfer ? snap.transfers.find(t => t.id === transfer.id) ?? transfer : null
  const newestSms = snap.sms[snap.sms.length - 1]
  const showSms = newestSms && newestSms.id !== dismissedSms && screen !== 'check'
  const ringing = snap.call && !snap.call.answered

  const doVerify = async () => setVerify(await api.verifyCall(clientId))
  const openCheck = (sampleId: string | null) => { setCheckSample(sampleId); setScreen('check'); if (newestSms) setDismissedSms(newestSms.id) }
  const toggleLang = async () => { await api.setLang(clientId, lang === 'kk' ? 'ru' : 'kk'); refresh() }

  return (
    <div className="relative flex h-full flex-col bg-slate-50 text-slate-900">
      {snap.call?.answered && <CallPill call={snap.call} lang={lang} onVerify={doVerify} onEnd={() => api.endCall(clientId).then(refresh)} />}
      <div className="flex-1 overflow-y-auto overscroll-contain">
        {screen === 'home' && (
          <Home snap={snap} lang={lang} onNav={setScreen} onVerify={doVerify} onCheck={openCheck} onToggleLang={toggleLang} />
        )}
        {screen === 'check' && <CheckScreen clientId={clientId} lang={lang} initialSample={checkSample} onBack={() => setScreen('home')} />}
        {screen === 'transfer' && (
          <TransferScreen clientId={clientId} lang={lang} prefill={snap.prefill} balance={snap.client.balance}
            onBack={() => setScreen('home')} onDone={t => { setTransfer(t); setScreen('result') }} />
        )}
        {screen === 'result' && liveTransfer && (
          <ResultScreen clientId={clientId} lang={lang} transfer={liveTransfer} onUpdate={setTransfer}
            onHome={() => { setScreen('home'); setTransfer(null) }} onVictim={() => setScreen('victim')} />
        )}
        {screen === 'victim' && <VictimScreen clientId={clientId} lang={lang} transferId={transfer?.id} onBack={() => setScreen('home')} />}
        {screen === 'schemes' && <SchemesScreen lang={lang} onBack={() => setScreen('home')} />}
      </div>

      {showSms && !ringing && <SmsBanner sms={newestSms} lang={lang} onOpen={() => openCheck(newestSms.sample_id)} onClose={() => setDismissedSms(newestSms.id)} />}
      {verify && <VerifySheet result={verify} lang={lang} onClose={() => setVerify(null)} />}
      {snap.family_requests[0] && <FamilySheet req={snap.family_requests[0]} lang={lang} onDone={refresh} />}
      {ringing && snap.call && (
        <IncomingCall call={snap.call} lang={lang} onAccept={() => api.answerCall(clientId).then(refresh)}
          onDecline={() => api.endCall(clientId).then(refresh)} />
      )}
    </div>
  )
}

function Home({ snap, lang, onNav, onVerify, onCheck, onToggleLang }: {
  snap: Snapshot; lang: Lang; onNav: (s: Screen) => void; onVerify: () => void; onCheck: (s: string | null) => void; onToggleLang: () => void
}) {
  const L = (k: Parameters<typeof tr>[1]) => tr(lang, k)
  const [schemes, setSchemes] = useState<{ id: string; title: string }[]>([])
  useEffect(() => { api.schemes(lang).then(setSchemes).catch(() => setSchemes([])) }, [lang])
  const actions = [
    { icon: 'send', label: L('transfer'), on: () => onNav('transfer'), tone: 'bg-teal-700 text-white' },
    { icon: 'msg', label: L('check_msg'), on: () => onCheck(null), tone: 'bg-white text-teal-800' },
    { icon: 'phone', label: L('bank_calling'), on: onVerify, tone: 'bg-white text-teal-800' },
    { icon: 'help', label: L('scammed'), on: () => onNav('victim'), tone: 'bg-white text-red-700' },
  ]
  return (
    <div className="space-y-4 px-4 pb-8 pt-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-teal-100 font-bold text-teal-800">{snap.client.avatar}</div>
          <div>
            <div className="text-xs text-slate-500">{L('hello')},</div>
            <div className="font-bold">{snap.client.short}</div>
          </div>
        </div>
        <button onClick={onToggleLang} className="rounded-full bg-white px-3 py-1.5 text-xs font-bold text-slate-700 ring-1 ring-slate-200">
          {lang === 'kk' ? 'ҚАЗ' : 'РУС'}
        </button>
      </div>

      <div className="rounded-3xl bg-gradient-to-br from-teal-700 to-teal-900 p-5 text-white shadow-lg">
        <div className="text-sm text-teal-100">{L('balance')}</div>
        <div className="mt-1 text-3xl font-bold tracking-tight">{money(snap.client.balance)}</div>
        <div className="mt-4 flex items-center gap-2 text-xs text-teal-100">
          <Icon name="shield" className="h-4 w-4" /> {L('qalqan_on')}
          {snap.client.guardian && <span className="ml-auto rounded-full bg-white/15 px-2 py-0.5">{L('family_shield')}: {snap.client.guardian}</span>}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {actions.map(a => (
          <button key={a.label} onClick={a.on} className="flex flex-col items-center gap-1.5 text-center">
            <span className={`grid h-14 w-14 place-items-center rounded-2xl shadow-sm ring-1 ring-slate-100 ${a.tone}`}><Icon name={a.icon} className="h-6 w-6" /></span>
            <span className="text-[11px] font-medium leading-tight text-slate-700">{a.label}</span>
          </button>
        ))}
      </div>

      {snap.sms.length > 0 && (
        <Card>
          <div className="mb-2 text-sm font-semibold text-slate-500">{L('sms')}</div>
          {snap.sms.slice().reverse().map(s => (
            <button key={s.id} onClick={() => onCheck(s.sample_id)} className="flex w-full gap-3 border-t border-slate-100 py-2 text-left first:border-0">
              <Icon name="msg" className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
              <div className="min-w-0">
                <div className="text-sm font-semibold">{s.sender}</div>
                <div className="line-clamp-2 text-xs text-slate-600">{s.text}</div>
                <div className="mt-1 text-[11px] font-semibold text-teal-700">{L('tap_to_check')} →</div>
              </div>
            </button>
          ))}
        </Card>
      )}

      {snap.transfers.length > 0 && (
        <Card>
          <div className="mb-2 text-sm font-semibold text-slate-500">{L('recent')}</div>
          {snap.transfers.slice().reverse().map(t => (
            <div key={t.id} className="flex items-center justify-between border-t border-slate-100 py-2 text-sm first:border-0">
              <div>
                <div className="font-medium">{t.holder}</div>
                <div className="text-xs text-slate-500">{t.title}</div>
              </div>
              <div className={t.status === 'completed' ? 'font-semibold' : 'font-semibold text-slate-400 line-through'}>−{money(t.amount)}</div>
            </div>
          ))}
        </Card>
      )}

      {schemes.length > 0 && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-500">{L('new_schemes')}</span>
            <button onClick={() => onNav('schemes')} className="text-xs font-semibold text-teal-700">→</button>
          </div>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
            {schemes.map(s => (
              <button key={s.id} onClick={() => onNav('schemes')} className="w-40 shrink-0 rounded-2xl bg-amber-50 p-3 text-left ring-1 ring-amber-100">
                <Icon name="news" className="h-5 w-5 text-amber-600" />
                <div className="mt-2 text-xs font-semibold leading-snug text-amber-900">{s.title}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
