import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type CallVerify, type Lang, type Snapshot, type TransferView } from '../api'
import { tr } from '../i18n'
import { useNativeCallSignal } from '../native'
import { FamilyScreen, FamilySheet, PushBanner } from './family'
import { Home } from './home'
import { CallPill, IncomingCall, SmsBanner, VerifySheet } from './overlays'
import { CheckScreen, ResultScreen, SchemesScreen, TransferScreen, VictimScreen } from './screens'

export type Screen = 'home' | 'check' | 'transfer' | 'result' | 'victim' | 'schemes' | 'family'

export default function BankApp({ clientId }: { clientId: string }) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [offline, setOffline] = useState(false)
  const [screen, setScreen] = useState<Screen>('home')
  const [transfer, setTransfer] = useState<TransferView | null>(null)
  const [checkSample, setCheckSample] = useState<string | null>(null)
  const [verify, setVerify] = useState<CallVerify | null>(null)
  const [dismissedSms, setDismissedSms] = useState<string | null>(null)
  const [openRequest, setOpenRequest] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const navSeq = useRef(0)
  const mountedAt = useRef(Date.now())
  const [bannerSms, setBannerSms] = useState<string | null>(null)
  useNativeCallSignal(clientId)

  const refresh = useCallback(async () => {
    try { setSnap(await api.phone(clientId)); setOffline(false) } catch { setOffline(true) }
  }, [clientId])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 900)
    return () => clearInterval(t)
  }, [refresh])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  // director-driven navigation (prefilled transfer, victim help); each nav fires once
  useEffect(() => {
    const nav = snap?.nav
    // director commands are one-shot: ignore anything issued before this page was opened
    if (!nav || nav.seq <= navSeq.current || nav.seq < mountedAt.current - 1000) return
    navSeq.current = nav.seq
    if (nav.screen === 'transfer' || nav.screen === 'victim') setScreen(nav.screen)
  }, [snap?.nav])

  // SMS banner: only for messages that arrive while the app is open, hides itself like a real notification
  const lastSmsId = snap?.sms[snap.sms.length - 1]?.id
  const lastSmsTs = snap?.sms[snap.sms.length - 1]?.ts
  useEffect(() => {
    if (!lastSmsId || !lastSmsTs || lastSmsTs * 1000 < mountedAt.current - 1000) return
    setBannerSms(lastSmsId)
    const t = setTimeout(() => setBannerSms(null), 7000)
    return () => clearTimeout(t)
  }, [lastSmsId, lastSmsTs])

  // demo reset on the server: every phone returns to a clean home screen
  const epoch = useRef<number | null>(null)
  useEffect(() => {
    if (snap?.epoch === undefined) return
    if (epoch.current !== null && snap.epoch !== epoch.current) {
      setScreen('home'); setTransfer(null); setVerify(null); setCheckSample(null); setDismissedSms(null); setOpenRequest(null)
    }
    epoch.current = snap.epoch
  }, [snap?.epoch])

  if (!snap) {
    return <div className="grid h-full place-items-center p-6 text-center text-sm text-slate-400">{offline ? 'Нет связи с сервером…' : '…'}</div>
  }
  const lang: Lang = snap.client.lang
  const L = (k: Parameters<typeof tr>[1]) => tr(lang, k)
  const liveTransfer = transfer ? snap.transfers.find(t => t.id === transfer.id) ?? transfer : null
  const newestSms = snap.sms[snap.sms.length - 1]
  const ringing = !!snap.call && !snap.call.answered
  const request = openRequest ? snap.family_requests.find(r => r.id === openRequest) : undefined
  const notice = snap.notices[snap.notices.length - 1]
  const showSms = !!newestSms && bannerSms === newestSms.id && newestSms.id !== dismissedSms && screen !== 'check' && !notice

  const doVerify = async () => {
    try { setVerify(await api.verifyCall(clientId)) } catch (e) { setToast(e instanceof Error ? e.message : L('error')) }
  }
  const openCheck = (sampleId: string | null) => { setCheckSample(sampleId); setScreen('check'); if (newestSms) setDismissedSms(newestSms.id) }
  const toggleLang = async () => { try { await api.setLang(clientId, lang === 'kk' ? 'ru' : 'kk'); refresh() } catch { /* keep */ } }
  const openNotice = () => {
    if (!notice) return
    api.noticeSeen(clientId, notice.id).catch(() => undefined)
    if (notice.kind === 'family_request' && notice.ref) setOpenRequest(notice.ref)
    else setScreen('family')
    refresh()
  }

  return (
    <div className="relative flex h-full flex-col bg-slate-50 text-slate-900">
      {offline && <div className="z-20 bg-amber-500 px-3 py-1 text-center text-xs font-semibold text-white">Нет связи с сервером — повторяем…</div>}
      {snap.call?.answered && <CallPill call={snap.call} lang={lang} onVerify={doVerify} onEnd={() => api.endCall(clientId).then(refresh).catch(() => undefined)} />}
      <div className="flex-1 overflow-y-auto overscroll-contain">
        {screen === 'home' && (
          <Home snap={snap} lang={lang} onNav={setScreen} onVerify={doVerify} onCheck={openCheck} onToggleLang={toggleLang}
            onOpenRequest={setOpenRequest} />
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
        {screen === 'family' && <FamilyScreen clientId={clientId} lang={lang} shield={snap.shield} onBack={() => setScreen('home')} onChanged={refresh} />}
      </div>

      {showSms && !ringing && <SmsBanner sms={newestSms} lang={lang} belowCall={!!snap.call?.answered} onOpen={() => openCheck(newestSms.sample_id)} onClose={() => setDismissedSms(newestSms.id)} />}
      {notice && !ringing && !request && (
        <PushBanner notice={notice} lang={lang} onOpen={openNotice} onClose={() => { api.noticeSeen(clientId, notice.id).then(refresh).catch(() => undefined) }} />
      )}
      {verify && <VerifySheet result={verify} lang={lang} onClose={() => setVerify(null)} />}
      {request && <FamilySheet req={request} lang={lang} onClose={() => setOpenRequest(null)}
        onDone={() => { setOpenRequest(null); refresh() }} />}
      {ringing && snap.call && (
        <IncomingCall call={snap.call} lang={lang} onAccept={() => api.answerCall(clientId).then(refresh).catch(() => undefined)}
          onDecline={() => api.endCall(clientId).then(refresh).catch(() => undefined)} />
      )}
      {toast && <div className="absolute inset-x-4 bottom-4 z-50 rounded-2xl bg-slate-900 p-3 text-center text-sm text-white shadow-xl">{toast}</div>}
    </div>
  )
}
