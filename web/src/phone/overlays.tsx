import { motion } from 'framer-motion'
import { useEffect, useState, type ReactNode } from 'react'
import { type CallVerify, type Lang, type Sms, type Snapshot } from '../api'
import { tr } from '../i18n'
import { buzz, EASE, SPRING } from '../motion'
import { Button, Icon } from '../ui'

type Call = NonNullable<Snapshot['call']>

function useElapsed(since: number) {
  const [now, setNow] = useState(Date.now() / 1000)
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t) }, [])
  const s = Math.max(0, Math.floor(now - since))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function IncomingCall({ call, lang, onAccept, onDecline }: { call: Call; lang: Lang; onAccept: () => void; onDecline: () => void }) {
  useEffect(() => { buzz([300, 150, 300, 150, 300]) }, [])
  return (
    <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.35, ease: EASE }}
      className="absolute inset-0 z-40 flex flex-col items-center justify-between bg-gradient-to-b from-slate-800 to-slate-950 px-6 pb-[max(4rem,env(safe-area-inset-bottom))] pt-16 text-white">
      <div className="text-center">
        <div className="text-sm text-slate-300">{tr(lang, 'incoming')}</div>
        <div className="mt-3 text-3xl font-semibold">{call.label}</div>
        <div className="mt-2 text-sm text-slate-400">Казахстан</div>
      </div>
      <div className="relative grid h-28 w-28 place-items-center">
        <motion.span className="absolute inset-0 rounded-full bg-white/10" animate={{ scale: [1, 1.35], opacity: [0.6, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }} />
        <span className="grid h-28 w-28 place-items-center rounded-full bg-white/10"><Icon name="phone" className="h-12 w-12" /></span>
      </div>
      <div className="flex w-full justify-around">
        <motion.button whileTap={{ scale: 0.9 }} onClick={onDecline} className="flex flex-col items-center gap-2">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-red-500"><Icon name="x" className="h-7 w-7" /></span>
          <span className="text-sm">{tr(lang, 'decline')}</span>
        </motion.button>
        <motion.button data-tour="call-accept" whileTap={{ scale: 0.9 }} onClick={onAccept} className="flex flex-col items-center gap-2">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-emerald-500"><Icon name="phone" className="h-7 w-7" /></span>
          <span className="text-sm">{tr(lang, 'accept')}</span>
        </motion.button>
      </div>
    </motion.div>
  )
}

export function CallPill({ call, lang, onVerify, onEnd }: { call: Call; lang: Lang; onVerify: () => void; onEnd: () => void }) {
  const elapsed = useElapsed(call.since)
  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.3, ease: EASE }} className="z-20 shrink-0 overflow-hidden bg-emerald-600 text-white">
      <div className="space-y-2 px-3 pb-2.5 pt-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="relative flex h-2 w-2"><span className="absolute h-2 w-2 animate-ping rounded-full bg-white/70" /><span className="h-2 w-2 rounded-full bg-white" /></span>
          <span className="font-semibold">{tr(lang, 'on_call')} · {elapsed}</span>
          <span className="truncate opacity-80">{call.label}</span>
          <motion.button whileTap={{ scale: 0.85 }} onClick={onEnd} className="ml-auto rounded-full bg-red-500 p-1.5" aria-label={tr(lang, 'end_call')}><Icon name="x" className="h-3.5 w-3.5" /></motion.button>
        </div>
        <motion.button data-tour="verify" whileTap={{ scale: 0.97 }} onClick={onVerify} className="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-2 text-sm font-bold text-emerald-700">
          <Icon name="shield" className="h-4 w-4" />{tr(lang, 'bank_calling')}
        </motion.button>
      </div>
    </motion.div>
  )
}

export function SmsBanner({ sms, lang, onOpen, onClose, belowCall = false }: { sms: Sms; lang: Lang; onOpen: () => void; onClose: () => void; belowCall?: boolean }) {
  useEffect(() => { buzz(40) }, [])
  return (
    <motion.div initial={{ y: -140, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -140, opacity: 0 }} transition={SPRING}
      drag="y" dragConstraints={{ top: 0, bottom: 0 }} onDragEnd={(_, i) => { if (i.offset.y < -30) onClose() }}
      className={`absolute inset-x-2 z-30 ${belowCall ? 'top-[92px]' : 'top-2'}`}>
      <div className="rounded-2xl bg-white/95 p-3 shadow-xl ring-1 ring-slate-200 backdrop-blur">
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-500 text-white"><Icon name="msg" className="h-5 w-5" /></span>
          <button onClick={onOpen} className="min-w-0 flex-1 text-left">
            <div className="text-sm font-semibold">{sms.sender}</div>
            <div className="line-clamp-2 text-xs text-slate-600">{sms.text}</div>
            <div className="mt-1 text-[11px] font-semibold text-teal-700">Qaqpan · {tr(lang, 'tap_to_check')}</div>
          </button>
          <button onClick={onClose} className="text-slate-400" aria-label="close"><Icon name="x" className="h-4 w-4" /></button>
        </div>
      </div>
    </motion.div>
  )
}

/** Bottom sheet: dimmed backdrop + panel that slides up, can be dragged down to close. */
export function Sheet({ onClose, children, z = 'z-30' }: { onClose: () => void; children: ReactNode; z?: string }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}
      className={`absolute inset-0 ${z} flex items-end bg-black/40`} onClick={onClose}>
      <motion.div initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }} transition={SPRING}
        drag="y" dragConstraints={{ top: 0, bottom: 0 }} dragElastic={{ top: 0, bottom: 0.6 }}
        onDragEnd={(_, i) => { if (i.offset.y > 80 || i.velocity.y > 500) onClose() }}
        className="w-full rounded-t-3xl bg-white px-5 pb-[max(2rem,env(safe-area-inset-bottom))] pt-2" onClick={e => e.stopPropagation()}>
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-slate-200" />
        {children}
      </motion.div>
    </motion.div>
  )
}

export function VerifySheet({ result, lang, onClose }: { result: CallVerify; lang: Lang; onClose: () => void }) {
  const tone = result.status === 'not_bank' ? 'bg-red-600' : result.status === 'bank' ? 'bg-emerald-600' : 'bg-slate-600'
  const icon = result.status === 'not_bank' ? 'alert' : result.status === 'bank' ? 'check' : 'phone'
  useEffect(() => { if (result.status === 'not_bank') buzz([80, 60, 80]) }, [result.status])
  return (
    <Sheet onClose={onClose}>
      <div data-tour="verify-sheet">
      <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ ...SPRING, delay: 0.1 }}
        className={`mx-auto grid h-16 w-16 place-items-center rounded-full text-white ${tone}`}><Icon name={icon} className="h-8 w-8" /></motion.div>
      <h3 className="mt-4 text-center text-xl font-bold">{result.title}</h3>
      <p className="mt-2 text-center text-sm text-slate-600">{result.message}</p>
      </div>
      <Button tour="verify-done" className="mt-5" tone={result.status === 'not_bank' ? 'danger' : 'primary'} onClick={onClose}>{tr(lang, 'done')}</Button>
    </Sheet>
  )
}
