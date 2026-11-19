import { useEffect, useState } from 'react'
import { type CallVerify, type Lang, type Sms, type Snapshot } from '../api'
import { tr } from '../i18n'
import { Button, Icon } from '../ui'

type Call = NonNullable<Snapshot['call']>

function useElapsed(since: number) {
  const [now, setNow] = useState(Date.now() / 1000)
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t) }, [])
  const s = Math.max(0, Math.floor(now - since))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function IncomingCall({ call, lang, onAccept, onDecline }: { call: Call; lang: Lang; onAccept: () => void; onDecline: () => void }) {
  return (
    <div className="absolute inset-0 z-40 flex flex-col items-center justify-between bg-gradient-to-b from-slate-800 to-slate-950 px-6 py-16 text-white">
      <div className="text-center">
        <div className="text-sm text-slate-300">{tr(lang, 'incoming')}</div>
        <div className="mt-3 text-3xl font-semibold">{call.label}</div>
        <div className="mt-2 text-sm text-slate-400">Казахстан</div>
      </div>
      <div className="grid h-28 w-28 animate-pulse place-items-center rounded-full bg-white/10"><Icon name="phone" className="h-12 w-12" /></div>
      <div className="flex w-full justify-around">
        <button onClick={onDecline} className="flex flex-col items-center gap-2">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-red-500"><Icon name="x" className="h-7 w-7" /></span>
          <span className="text-sm">{tr(lang, 'decline')}</span>
        </button>
        <button onClick={onAccept} className="flex flex-col items-center gap-2">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-emerald-500"><Icon name="phone" className="h-7 w-7" /></span>
          <span className="text-sm">{tr(lang, 'accept')}</span>
        </button>
      </div>
    </div>
  )
}

export function CallPill({ call, lang, onVerify, onEnd }: { call: Call; lang: Lang; onVerify: () => void; onEnd: () => void }) {
  const elapsed = useElapsed(call.since)
  return (
    <div className="z-20 space-y-2 bg-emerald-600 px-3 pb-2.5 pt-2 text-white">
      <div className="flex items-center gap-2 text-xs">
        <Icon name="phone" className="h-4 w-4" />
        <span className="font-semibold">{tr(lang, 'on_call')} · {elapsed}</span>
        <span className="truncate opacity-80">{call.label}</span>
        <button onClick={onEnd} className="ml-auto rounded-full bg-red-500 p-1.5" aria-label={tr(lang, 'end_call')}><Icon name="x" className="h-3.5 w-3.5" /></button>
      </div>
      <button onClick={onVerify} className="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-2 text-sm font-bold text-emerald-700">
        <Icon name="shield" className="h-4 w-4" />{tr(lang, 'bank_calling')}
      </button>
    </div>
  )
}

export function SmsBanner({ sms, lang, onOpen, onClose, belowCall = false }: { sms: Sms; lang: Lang; onOpen: () => void; onClose: () => void; belowCall?: boolean }) {
  return (
    <div className={`absolute inset-x-2 z-30 ${belowCall ? 'top-[92px]' : 'top-2'}`}>
    <div className="animate-[slidein_.35s_ease-out] rounded-2xl bg-white/95 p-3 shadow-xl ring-1 ring-slate-200 backdrop-blur">
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
    </div>
  )
}

export function VerifySheet({ result, lang, onClose }: { result: CallVerify; lang: Lang; onClose: () => void }) {
  const tone = result.status === 'not_bank' ? 'bg-red-600' : result.status === 'bank' ? 'bg-emerald-600' : 'bg-slate-600'
  const icon = result.status === 'not_bank' ? 'alert' : result.status === 'bank' ? 'check' : 'phone'
  return (
    <div className="absolute inset-0 z-30 flex items-end bg-black/40" onClick={onClose}>
      <div className="w-full animate-[slideup_.3s_ease-out] rounded-t-3xl bg-white p-5 pb-8" onClick={e => e.stopPropagation()}>
        <div className={`mx-auto grid h-16 w-16 place-items-center rounded-full text-white ${tone}`}><Icon name={icon} className="h-8 w-8" /></div>
        <h3 className="mt-4 text-center text-xl font-bold">{result.title}</h3>
        <p className="mt-2 text-center text-sm text-slate-600">{result.message}</p>
        <Button className="mt-5" tone={result.status === 'not_bank' ? 'danger' : 'primary'} onClick={onClose}>{tr(lang, 'done')}</Button>
      </div>
    </div>
  )
}
