import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type CallVerify, type Lang, type Snapshot, type TransferView } from '../api'
import { tr } from '../i18n'
import { DEPTH, pageVariants } from '../motion'
import { useNativeCallSignal } from '../native'
import { useLargeText, useTheme } from '../theme'
import { FamilyScreen, FamilySheet, PushBanner } from './family'
import { AssistantScreen } from './assistant'
import { Home } from './home'
import { CallPill, IncomingCall, SmsBanner, VerifySheet } from './overlays'
import { CheckScreen, ResultScreen, SchemesScreen, TransferScreen, VictimScreen } from './screens'

export type Screen = 'home' | 'check' | 'transfer' | 'result' | 'victim' | 'schemes' | 'family' | 'assistant'

export default function BankApp({ clientId }: { clientId: string }) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const theme = useTheme()
  const large = useLargeText()
  const [offline, setOffline] = useState(false)
  const [screen, setScreenRaw] = useState<Screen>('home')
  const [dir, setDir] = useState(1)
  const screenRef = useRef<Screen>('home')
  const setScreen = useCallback((next: Screen) => {
    if (next === screenRef.current) return
    setDir((DEPTH[next] ?? 1) >= (DEPTH[screenRef.current] ?? 0) ? 1 : -1)
    screenRef.current = next
    setScreenRaw(next)
  }, [])
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
  }, [snap?.nav, setScreen])

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
  }, [snap?.epoch, setScreen])

  if (!snap) {
    return (
      <div className="grid h-full place-items-center bg-slate-50 p-6 text-center">
        <div>
          <motion.div animate={{ scale: [1, 1.08, 1] }} transition={{ duration: 1.2, repeat: Infinity }}
            className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-teal-700 text-white">
            <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" /></svg>
          </motion.div>
          <div className="mt-3 text-sm text-slate-400">{offline ? 'Нет связи с сервером…' : 'Qaqpan'}</div>
        </div>
      </div>
    )
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

  const page = (() => {
    switch (screen) {
      case 'home': return <Home snap={snap} lang={lang} onNav={setScreen} onVerify={doVerify} onCheck={openCheck} onToggleLang={toggleLang} onOpenRequest={setOpenRequest} />
      case 'check': return <CheckScreen clientId={clientId} lang={lang} initialSample={checkSample} onBack={() => setScreen('home')} />
      case 'transfer': return <TransferScreen clientId={clientId} lang={lang} prefill={snap.prefill} balance={snap.client.balance}
        onBack={() => setScreen('home')} onDone={t => { setTransfer(t); setScreen('result') }} />
      case 'result': return liveTransfer ? <ResultScreen clientId={clientId} lang={lang} transfer={liveTransfer} onUpdate={setTransfer}
        onHome={() => { setScreen('home'); setTransfer(null) }} onVictim={() => setScreen('victim')} /> : null
      case 'victim': return <VictimScreen clientId={clientId} lang={lang} transferId={transfer?.id} onBack={() => setScreen('home')} />
      case 'schemes': return <SchemesScreen lang={lang} onBack={() => setScreen('home')} />
      case 'assistant': return <AssistantScreen clientId={clientId} lang={lang} onBack={() => setScreen('home')} />
      case 'family': return <FamilyScreen clientId={clientId} lang={lang} shield={snap.shield} onBack={() => setScreen('home')} onChanged={refresh} />
    }
  })()

  return (
    <div className={`relative flex h-full w-full flex-col overflow-hidden bg-slate-50 text-slate-900 ${theme === 'bcc' ? 'theme-bcc' : ''} ${large ? 'qq-large' : ''}`}>
      <AnimatePresence initial={false}>
        {offline && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="z-20 shrink-0 overflow-hidden bg-amber-500 text-center text-xs font-semibold text-white">
            <div className="px-3 py-1">Нет связи с сервером — повторяем…</div>
          </motion.div>
        )}
        {snap.call?.answered && <CallPill key="pill" call={snap.call} lang={lang} onVerify={doVerify} onEnd={() => api.endCall(clientId).then(refresh).catch(() => undefined)} />}
      </AnimatePresence>

      <div className="relative flex-1 overflow-hidden">
        <AnimatePresence initial={false} custom={dir}>
          <motion.div key={screen} custom={dir} variants={pageVariants} initial="enter" animate="center" exit="exit"
            className="absolute inset-0 overflow-y-auto overscroll-contain bg-slate-50 shadow-[-8px_0_24px_rgba(15,23,42,0.06)]">
            {page}
          </motion.div>
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {showSms && !ringing && <SmsBanner key={`sms-${newestSms.id}`} sms={newestSms} lang={lang} belowCall={!!snap.call?.answered}
          onOpen={() => openCheck(newestSms.sample_id)} onClose={() => setDismissedSms(newestSms.id)} />}
        {notice && !ringing && !request && (
          <PushBanner key={`n-${notice.id}`} notice={notice} lang={lang} onOpen={openNotice}
            onClose={() => { api.noticeSeen(clientId, notice.id).then(refresh).catch(() => undefined) }} />
        )}
        {verify && <VerifySheet key="verify" result={verify} lang={lang} onClose={() => setVerify(null)} />}
        {request && <FamilySheet key={`req-${request.id}`} req={request} clientId={clientId} lang={lang} onClose={() => setOpenRequest(null)}
          onDone={() => { setOpenRequest(null); refresh() }} />}
        {ringing && snap.call && (
          <IncomingCall key="incoming" call={snap.call} lang={lang} onAccept={() => api.answerCall(clientId).then(refresh).catch(() => undefined)}
            onDecline={() => api.endCall(clientId).then(refresh).catch(() => undefined)} />
        )}
        {toast && (
          <motion.div key="toast" initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
            className="absolute inset-x-4 bottom-4 z-50 rounded-2xl bg-slate-900 p-3 text-center text-sm text-white shadow-xl">{toast}</motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
