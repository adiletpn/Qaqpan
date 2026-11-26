import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api, money, type CheckResult, type DelayAnalysis, type Lang, type RecipientCheck, type Sample, type SchemeCard, type Snapshot, type TransferView, type VictimHelp } from '../api'
import { tr } from '../i18n'
import { buzz, EASE, sleep, SPRING } from '../motion'
import { Button, Card, Header, Icon, Spinner } from '../ui'
import { Evidence } from './Evidence'
import { SpeakButton } from './Speak'
import { Thinking } from './Thinking'

type K = Parameters<typeof tr>[1]

// ------------------------------------------------------------------ layer 1: check a message

export function CheckScreen({ clientId, lang, initialSample, onBack }: { clientId: string; lang: Lang; initialSample: string | null; onBack: () => void }) {
  const L = (k: K) => tr(lang, k)
  const [samples, setSamples] = useState<Sample[]>([])
  const [text, setText] = useState('')
  const [sample, setSample] = useState<string | null>(initialSample)
  const [upload, setUpload] = useState<{ b64: string; type: string; url: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<CheckResult | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { api.samples().then(setSamples).catch(() => setSamples([])) }, [])
  const chosen = samples.find(s => s.id === sample)

  const onFile = (f: File | undefined) => {
    if (!f) return
    if (!f.type.startsWith('image/')) { setErr(L('error')); return }
    const reader = new FileReader()
    reader.onload = () => {
      // phone photos are 5–10 MB: downscale to ≤1600 px JPEG before sending
      const img = new Image()
      img.onload = () => {
        const k = Math.min(1, 1600 / Math.max(img.width, img.height))
        const cv = document.createElement('canvas')
        cv.width = Math.round(img.width * k); cv.height = Math.round(img.height * k)
        cv.getContext('2d')?.drawImage(img, 0, 0, cv.width, cv.height)
        const url = cv.toDataURL('image/jpeg', 0.85)
        setUpload({ b64: url.split(',')[1], type: 'image/jpeg', url })
        setSample(null); setRes(null); setErr(null)
      }
      img.onerror = () => setErr(L('error'))
      img.src = String(reader.result)
    }
    reader.readAsDataURL(f)
  }

  const run = async () => {
    setBusy(true); setErr(null); setRes(null)
    try {
      const [r] = await Promise.all([api.check({
        client_id: clientId, lang, text: text.trim() || undefined, sample_id: sample ?? undefined,
        image_b64: upload?.b64, media_type: upload?.type,
      }), sleep(450)])
      if (r.verdict !== 'safe') buzz([60, 40, 60])
      setRes(r)
    } catch (e) { setErr(e instanceof Error ? e.message : L('error')) } finally { setBusy(false) }
  }

  return (
    <div className="pb-8">
      <Header title={L('check_msg')} onBack={onBack} />
      <div className="space-y-3 px-4">
        <textarea value={text} onChange={e => { setText(e.target.value); setRes(null) }} placeholder={L('paste_hint')} rows={3}
          className="w-full resize-none rounded-2xl border-0 bg-white p-3 text-sm shadow-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-teal-600" />
        {(chosen || upload) && (
          <div className="relative overflow-hidden rounded-2xl ring-1 ring-slate-200">
            <img src={upload?.url ?? chosen?.image} alt="" className="max-h-56 w-full bg-white object-contain" />
            <button onClick={() => { setSample(null); setUpload(null); setRes(null) }} className="absolute right-2 top-2 rounded-full bg-black/50 p-1 text-white"><Icon name="x" className="h-4 w-4" /></button>
          </div>
        )}
        {!chosen && !upload && (
          <>
            <div className="text-xs font-semibold text-slate-500">{L('screenshots')}</div>
            <div className="grid grid-cols-4 gap-2">
              {samples.map(s => (
                <button key={s.id} onClick={() => { setSample(s.id); setRes(null) }} title={s.label[lang]} className="overflow-hidden rounded-xl ring-1 ring-slate-200">
                  <img src={s.image} alt={s.label[lang]} className="aspect-[4/5] w-full object-cover object-top" />
                </button>
              ))}
              <label className="grid aspect-[4/5] cursor-pointer place-items-center rounded-xl bg-white text-center text-[10px] font-semibold text-teal-700 ring-1 ring-dashed ring-teal-300">
                <span><Icon name="image" className="mx-auto mb-1 h-5 w-5" />{L('upload')}</span>
                <input type="file" accept="image/*" className="hidden" onChange={e => onFile(e.target.files?.[0])} />
              </label>
            </div>
          </>
        )}
        <Button tour="check-btn" onClick={run} disabled={busy || (!text.trim() && !sample && !upload)}>
          {busy ? <span className="flex items-center justify-center gap-2"><Spinner />{L('checking')}</span> : L('check')}
        </Button>
        {err && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</div>}
        {res && <Verdict res={res} lang={lang} />}
      </div>
    </div>
  )
}

function Verdict({ res, lang }: { res: CheckResult; lang: Lang }) {
  const L = (k: K) => tr(lang, k)
  const cfg = {
    scam: { bg: 'bg-red-600', ring: 'ring-red-200', icon: 'alert', label: L('scam') },
    suspicious: { bg: 'bg-amber-500', ring: 'ring-amber-200', icon: 'alert', label: L('suspicious') },
    safe: { bg: 'bg-emerald-600', ring: 'ring-emerald-200', icon: 'check', label: L('safe') },
  }[res.verdict]
  return (
    <motion.div data-tour="verdict" initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={SPRING}
      className={`overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ${cfg.ring}`}>
      <div className={`flex items-center gap-3 p-4 text-white ${cfg.bg}`}>
        <Icon name={cfg.icon} className="h-7 w-7" />
        <div>
          <div className="text-lg font-semibold">{cfg.label}</div>
          {res.scheme_name && <div className="text-sm opacity-90">{res.scheme_name}</div>}
        </div>
      </div>
      <div className="space-y-3 p-4">
        {res.text && res.reasons.some(r => r.spans?.length) ? <Evidence text={res.text} reasons={res.reasons} lang={lang} /> : (
          <ul className="space-y-1.5 text-sm">
            {res.reasons.map((r, i) => (
              <motion.li key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.08, duration: 0.3, ease: EASE }}
                className="flex gap-2"><span className="text-slate-400">•</span>{r.text}</motion.li>
            ))}
          </ul>
        )}
        {res.tip && (
          <div className="flex gap-2.5 rounded-2xl bg-teal-50 p-3 text-sm font-medium text-teal-900 ring-1 ring-teal-100">
            <Icon name="key" className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />{res.tip}
          </div>
        )}
        <div className="rounded-2xl bg-slate-50 p-3 text-sm font-medium">{res.advice}</div>
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-400">{res.source === 'rules' ? L('via_rules') : L('via_ai')}</span>
          <SpeakButton lang={lang} text={[cfg.label, res.scheme_name, ...res.reasons.map(r => r.text), res.tip, res.advice].filter(Boolean).join('. ')} />
        </div>
      </div>
    </motion.div>
  )
}

// ------------------------------------------------------------------ layer 3: transfer

export function TransferScreen({ clientId, lang, prefill, balance, onBack, onDone }: {
  clientId: string; lang: Lang; prefill: Snapshot['prefill']; balance: number; onBack: () => void; onDone: (t: TransferView) => void
}) {
  const L = (k: K) => tr(lang, k)
  const [account, setAccount] = useState(prefill?.account ?? '')
  const fmt = (v: string) => v.replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  const [amount, setAmount] = useState(prefill ? fmt(String(prefill.amount)) : '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const pasted = useRef(false)
  const switches = useRef(0)

  useEffect(() => {
    if (prefill) { setAccount(prefill.account); setAmount(fmt(String(prefill.amount))) }
  }, [prefill])
  // real behavioural signal: leaving the app while filling the form (e.g. to read a chat)
  useEffect(() => {
    const h = () => { if (document.visibilityState === 'hidden') switches.current += 1 }
    document.addEventListener('visibilitychange', h)
    return () => document.removeEventListener('visibilitychange', h)
  }, [])

  const amt = Number(amount.replace(/\s/g, ''))
  const [analyzing, setAnalyzing] = useState(false)
  const submit = async () => {
    setBusy(true); setErr(null); setAnalyzing(true)
    try {
      // the check takes milliseconds; a short visible analysis tells the client what Qaqpan looked at
      const [t] = await Promise.all([
        api.transfer({ client_id: clientId, account, amount: amt, context: { pasted: pasted.current, app_switches: switches.current } }),
        sleep(1400),
      ])
      onDone(t)
    } catch (e) { setErr(e instanceof Error ? e.message : L('error')); setAnalyzing(false) } finally { setBusy(false) }
  }

  return (
    <div className="relative min-h-full pb-8">
      <AnimatePresence>{analyzing && <Analysis key="an" lang={lang} />}</AnimatePresence>
      <Header title={L('transfer')} onBack={onBack} />
      <div className="space-y-4 px-4">
        <Card>
          <label className="text-xs font-semibold text-slate-500">{L('recipient')}</label>
          <input value={account} onChange={e => setAccount(e.target.value)} onPaste={() => { pasted.current = true }}
            placeholder="KZ00 0000 0000 0000 0000" className="mt-1 w-full border-0 p-0 font-mono text-[15px] focus:ring-0 focus:outline-none" />
          <RecipientBadge clientId={clientId} account={account} />
        </Card>
        <Card>
          <label className="text-xs font-semibold text-slate-500">{L('amount')}</label>
          <div className="mt-1 flex items-baseline gap-1">
            <input value={amount} onChange={e => setAmount(fmt(e.target.value))} inputMode="numeric" placeholder="0"
              className="w-full border-0 p-0 text-3xl font-semibold focus:outline-none focus:ring-0" />
            <span className="text-2xl font-semibold text-slate-400">₸</span>
          </div>
          <div className="mt-2 text-xs text-slate-500">{L('balance')}: {money(balance)}</div>
          {prefill?.note && <div className="mt-2 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{prefill.note}</div>}
        </Card>
        {err && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</div>}
        <Button tour="send" onClick={submit} disabled={busy || account.replace(/\D/g, '').length < 6 || !amt}>
          {busy ? <span className="flex items-center justify-center gap-2"><Spinner />…</span> : `${L('send')} ${amt ? money(amt) : ''}`}
        </Button>
        <div className="flex items-center justify-center gap-1.5 text-xs text-slate-400"><Icon name="shield" className="h-3.5 w-3.5" />{L('qaqpan_on')}</div>
      </div>
    </div>
  )
}

// «Проверить получателя»: as soon as the number is complete — only «complaints / no complaints», never the owner
function RecipientBadge({ clientId, account }: { clientId: string; account: string }) {
  const [res, setRes] = useState<RecipientCheck | null>(null)
  const digits = account.replace(/\D/g, '')
  useEffect(() => {
    setRes(null)
    if (digits.length < 12 || digits.length > 20) return
    const t = setTimeout(() => { api.checkRecipient(clientId, digits).then(setRes).catch(() => setRes(null)) }, 450)
    return () => clearTimeout(t)
  }, [clientId, digits])
  const tone = { complaints: 'bg-red-50 text-red-800 ring-red-200', signals: 'bg-amber-50 text-amber-900 ring-amber-200',
    own: 'bg-amber-50 text-amber-900 ring-amber-200', known: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
    clean: 'bg-slate-50 text-slate-600 ring-slate-200' }
  return (
    <AnimatePresence initial={false}>
      {res && (
        <motion.div key={res.status} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.22, ease: EASE }} className="overflow-hidden">
          <div className={`mt-2 flex gap-2 rounded-xl p-2.5 text-[13px] leading-snug ring-1 ${tone[res.status]}`}>
            <Icon name={res.status === 'known' || res.status === 'clean' ? 'check' : 'alert'} className="mt-0.5 h-4 w-4 shrink-0" />{res.message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// «Отложить на час»: a live countdown and what Qaqpan concluded meanwhile
function Countdown({ until, lang }: { until: number; lang: Lang }) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t) }, [])
  const left = Math.max(0, Math.round(until - now))
  const mm = String(Math.floor(left / 60)).padStart(2, '0'), ss = String(left % 60).padStart(2, '0')
  return (
    <div className="flex items-center justify-center gap-2 text-sm font-semibold text-slate-600">
      <Icon name="clock" className="h-4 w-4" />{tr(lang, 'goes_in')} <span className="font-mono tabular-nums text-slate-900">{mm}:{ss}</span>
    </div>
  )
}

function DelayCard({ a, lang }: { a: DelayAnalysis | null | undefined; lang: Lang }) {
  const tone = { likely_scam: 'bg-red-600', unclear: 'bg-amber-500', likely_ok: 'bg-emerald-600' }
  return (
    <div className="min-h-[56px]">
      <AnimatePresence mode="wait" initial={false}>
        {!a ? (
          <motion.div key="t" exit={{ opacity: 0 }} transition={{ duration: 0.2 }}><Thinking lang={lang} /></motion.div>
        ) : (
          <motion.div key="a" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={SPRING}
            className="overflow-hidden rounded-3xl bg-white text-left shadow-sm ring-1 ring-slate-100">
            <div className={`flex items-center gap-2 px-4 py-3 text-white ${tone[a.verdict]}`}>
              <Icon name={a.verdict === 'likely_ok' ? 'check' : 'alert'} className="h-5 w-5" />
              <div className="font-bold">{a.title}</div>
            </div>
            <div className="space-y-2 p-4 text-sm">
              <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{tr(lang, 'analysis')}</div>
              <ul className="space-y-1.5">
                {a.reasons.map((r, i) => (
                  <motion.li key={r} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.08, duration: 0.3, ease: EASE }}
                    className="flex gap-2"><span className="text-slate-400">•</span>{r}</motion.li>
                ))}
              </ul>
              <div className="rounded-2xl bg-slate-50 p-3 font-medium">{a.advice}</div>
              <div className="flex justify-end"><SpeakButton lang={lang} text={[a.title, ...a.reasons, a.advice].join('. ')} /></div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Analysis({ lang }: { lang: Lang }) {
  const L = (k: K) => tr(lang, k)
  const items: K[] = ['chk_recipient', 'chk_call', 'chk_amount']
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-50/95 px-8 backdrop-blur-sm">
      <div className="relative grid h-20 w-20 place-items-center">
        <motion.span className="absolute inset-0 rounded-full border-4 border-teal-200 border-t-teal-700"
          animate={{ rotate: 360 }} transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }} />
        <Icon name="shield" className="h-9 w-9 text-teal-700" />
      </div>
      <div className="mt-5 text-lg font-bold">{L('analyzing')}</div>
      <div className="mt-4 w-full space-y-2.5">
        {items.map((k, i) => (
          <motion.div key={k} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.35, duration: 0.3, ease: EASE }}
            className="flex items-center gap-3 rounded-2xl bg-white px-3 py-2.5 text-sm shadow-sm ring-1 ring-slate-100">
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.45 + i * 0.35, ...SPRING }}
              className="grid h-5 w-5 place-items-center rounded-full bg-teal-700 text-white"><Icon name="check" className="h-3 w-3" /></motion.span>
            {L(k)}
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

export function ResultScreen({ clientId, lang, transfer: t, onUpdate, onHome, onVictim }: {
  clientId: string; lang: Lang; transfer: TransferView; onUpdate: (t: TransferView) => void; onHome: () => void; onVictim: () => void
}) {
  const L = (k: K) => tr(lang, k)
  const [answers, setAnswers] = useState<(boolean | null)[]>([null, null, null])
  const [busy, setBusy] = useState(false)
  const [complained, setComplained] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const run = async (f: () => Promise<void>) => {
    setBusy(true); setErr(null)
    try { await f() } catch (e) { setErr(e instanceof Error ? e.message : L('error')) } finally { setBusy(false) }
  }
  const act = (f: () => Promise<TransferView>) => run(async () => onUpdate(await f()))
  const complain = () => run(async () => setComplained((await api.complain(clientId, t.id)).message))

  useEffect(() => {
    if (t.status === 'questions' || t.status === 'held') buzz([70, 50, 70])
    else if (t.status === 'cancelled') buzz(30)
  }, [t.status])

  const look = {
    completed: { bg: 'bg-emerald-600', icon: 'check' }, warning: { bg: 'bg-amber-500', icon: 'alert' },
    questions: { bg: 'bg-amber-500', icon: 'shield' }, awaiting_family: { bg: 'bg-teal-700', icon: 'family' },
    held: { bg: 'bg-red-600', icon: 'shield' }, escalated: { bg: 'bg-amber-600', icon: 'phone' }, cancelled: { bg: 'bg-emerald-600', icon: 'shield' },
    delayed: { bg: 'bg-teal-700', icon: 'clock' },
  }[t.status]

  return (
    <AnimatePresence mode="wait" initial={false}>
    <motion.div key={t.status} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.28, ease: EASE }} className="px-4 pb-8 pt-6">
      <div className="text-center" data-tour="result">
        <motion.div initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ ...SPRING, delay: 0.05 }}
          className={`mx-auto grid h-20 w-20 place-items-center rounded-full text-white shadow-lg ${look.bg}`}>
          {t.status === 'awaiting_family' ? <span className="h-8 w-8 animate-spin rounded-full border-4 border-white/30 border-t-white" /> : <Icon name={look.icon} className="h-10 w-10" />}
        </motion.div>
        <h2 className="mt-4 text-2xl font-bold leading-tight">{t.title}</h2>
        <div className="mt-1 text-sm text-slate-500">{money(t.amount)} → {t.holder}</div>
        {t.message && <p className="mt-3 text-[15px] leading-relaxed text-slate-700">{t.message}</p>}
        {t.message && <div className="mt-3 flex justify-center"><SpeakButton lang={lang} text={`${t.title ?? ''}. ${t.message}`} /></div>}
      </div>

      {err && <div className="mt-4 rounded-xl bg-red-50 p-3 text-center text-sm text-red-700">{err}</div>}

      {t.status === 'questions' && (
        <div className="mt-5 space-y-2" data-tour="questions">
          {t.questions.map((q, i) => (
            <motion.div key={q.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 + i * 0.07, duration: 0.3, ease: EASE }}>
            <Card className="!p-3">
              <div className="text-sm font-medium">{q.text}</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {[true, false].map(v => (
                  <button key={String(v)} onClick={() => setAnswers(a => a.map((x, j) => (j === i ? v : x)))}
                    className={`rounded-xl py-2 text-sm font-semibold ring-1 transition-all duration-150 active:scale-95 ${answers[i] === v ? (v ? 'bg-red-600 text-white ring-red-600' : 'bg-slate-800 text-white ring-slate-800') : 'bg-white text-slate-700 ring-slate-200'}`}>
                    {v ? L('yes') : L('no')}
                  </button>
                ))}
              </div>
            </Card>
            </motion.div>
          ))}
          <Button tour="answer" disabled={busy || answers.some(a => a === null)} onClick={() => act(() => api.answers(t.id, answers as boolean[]))}>{L('answer')}</Button>
          <Button tone="ghost" disabled={busy} onClick={() => act(() => api.cancel(t.id))}>{L('cancel')}</Button>
        </div>
      )}

      {t.status === 'warning' && (
        <div className="mt-6 space-y-2">
          <Button tone="success" disabled={busy} onClick={() => act(() => api.cancel(t.id))}>{L('cancel')}</Button>
          <Button tour="delay" tone="primary" disabled={busy} onClick={() => act(() => api.delay(t.id))}>
            <span className="flex flex-col items-center leading-tight"><span className="flex items-center gap-1.5"><Icon name="clock" className="h-4 w-4" />{L('delay')}</span>
              <span className="mt-0.5 text-[11px] font-normal opacity-80">{L('delay_hint')}</span></span>
          </Button>
          <Button tone="light" disabled={busy} onClick={() => act(() => api.proceed(t.id))}>{L('proceed')}</Button>
        </div>
      )}

      {t.status === 'delayed' && (
        <div className="mt-5 space-y-3" data-tour="delayed">
          {t.release_at && <Countdown until={t.release_at} lang={lang} />}
          <DelayCard a={t.analysis} lang={lang} />
          <Button tone="success" disabled={busy} onClick={() => act(() => api.cancel(t.id))}>{L('cancel')}</Button>
          <Button tone="light" onClick={onHome}>{L('home')}</Button>
        </div>
      )}

      {t.status === 'awaiting_family' && (
        <div className="mt-6 space-y-2">
          <div className="flex items-center justify-center gap-2 text-sm font-semibold text-teal-800"><Icon name="family" />{L('waiting_family')}: {t.guardian_name}</div>
          <Button tone="ghost" disabled={busy} onClick={() => act(() => api.cancel(t.id))}>{L('cancel')}</Button>
        </div>
      )}

      {(t.status === 'cancelled' || t.status === 'held' || t.status === 'escalated') && (
        <div className="mt-6 space-y-2">
          {complained
            ? <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={SPRING} className="rounded-2xl bg-emerald-50 p-3 text-center text-sm font-medium text-emerald-800 ring-1 ring-emerald-200">{complained}</motion.div>
            : <Button tour="complain" tone="danger" disabled={busy} onClick={complain}>{L('complain')}</Button>}
          <Button tone="light" onClick={onHome}>{L('home')}</Button>
          <Button tone="ghost" onClick={onVictim}>{L('already_sent')}</Button>
        </div>
      )}

      {t.status === 'completed' && <div className="mt-6"><Button onClick={onHome}>{L('home')}</Button></div>}
    </motion.div>
    </AnimatePresence>
  )
}

// ------------------------------------------------------------------ help & schemes

export function VictimScreen({ clientId, lang, transferId, onBack }: { clientId: string; lang: Lang; transferId?: string; onBack: () => void }) {
  const L = (k: K) => tr(lang, k)
  const [story, setStory] = useState('')
  const [help, setHelp] = useState<VictimHelp | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  useEffect(() => { api.victim(clientId, lang, transferId).then(setHelp).catch(() => setHelp(null)) }, [clientId, lang, transferId])
  const build = async () => {
    setBusy(true)
    try { setHelp(await api.victim(clientId, lang, transferId, story)) } catch { /* keep the template version */ } finally { setBusy(false) }
  }
  const copy = async () => {
    if (!help) return
    try { await navigator.clipboard.writeText(`${help.statement.title}\n\n${help.statement.body}`); setCopied(true) } catch { setCopied(false) }
  }
  return (
    <div className="pb-8">
      <Header title={L('victim_title')} onBack={onBack} />
      <div className="space-y-3 px-4">
        {help && (
          <Card className="!bg-red-50 ring-red-100">
            <div className="mb-2 text-sm font-bold text-red-800">{L('steps')}</div>
            <ol className="space-y-2 text-sm text-red-950">
              {help.steps.map((s, i) => <li key={i} className="flex gap-2"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-red-600 text-[11px] font-bold text-white">{i + 1}</span>{s}</li>)}
            </ol>
          </Card>
        )}
        <textarea value={story} onChange={e => setStory(e.target.value)} placeholder={L('story_hint')} rows={2}
          className="w-full resize-none rounded-2xl border-0 bg-white p-3 text-sm shadow-sm ring-1 ring-slate-200" />
        <Button onClick={build} disabled={busy}>{busy ? <span className="flex items-center justify-center gap-2"><Spinner />…</span> : L('make_statement')}</Button>
        {help && (
          <Card>
            <div className="text-sm font-bold">{help.statement.title}</div>
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700">{help.statement.body}</p>
            <Button tone="light" className="mt-3" onClick={copy}>{copied ? L('copied') : L('copy')}</Button>
          </Card>
        )}
      </div>
    </div>
  )
}

export function SchemesScreen({ lang, onBack }: { lang: Lang; onBack: () => void }) {
  const L = (k: K) => tr(lang, k)
  const [cards, setCards] = useState<SchemeCard[]>([])
  useEffect(() => { api.schemes(lang).then(setCards).catch(() => setCards([])) }, [lang])
  return (
    <div className="pb-8">
      <Header title={L('new_schemes')} onBack={onBack} />
      <div className="space-y-3 px-4">
        {cards.map(c => (
          <Card key={c.id}>
            <div className="text-[11px] font-semibold text-amber-600">{c.date}</div>
            <div className="font-bold">{c.title}</div>
            <p className="mt-1 text-sm text-slate-700">{c.how}</p>
            <div className="mt-2 rounded-xl bg-emerald-50 p-2 text-sm text-emerald-900"><b>{L('sign')}:</b> {c.sign}</div>
            <a href={c.source} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-semibold text-teal-700">{L('source')} ↗</a>
          </Card>
        ))}
      </div>
    </div>
  )
}
