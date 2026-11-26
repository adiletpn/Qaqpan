import { useEffect, useState } from 'react'
import { api, money, type Lang, type Snapshot } from '../api'
import { tr } from '../i18n'
import { Icon } from '../ui'
import type { Screen } from './BankApp'
import { setLargeText, useLargeText } from '../theme'

type K = Parameters<typeof tr>[1]

const CARD_TAIL: Record<string, string> = { aigerim: '4521', erzhan: '7310', madina: '0942' }

function when(ts: number, lang: Lang) {
  const d = new Date(ts * 1000)
  const now = new Date()
  const hm = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  const day = (x: Date) => x.toDateString()
  if (day(d) === day(now)) return `${tr(lang, 'today')}, ${hm}`
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (day(d) === day(y)) return `${tr(lang, 'yesterday')}, ${hm}`
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

export function Home({ snap, lang, onNav, onVerify, onCheck, onToggleLang, onOpenRequest }: {
  snap: Snapshot; lang: Lang; onNav: (s: Screen) => void; onVerify: () => void; onCheck: (s: string | null) => void
  onToggleLang: () => void; onOpenRequest: (id: string) => void
}) {
  const large = useLargeText()
  const L = (k: K) => tr(lang, k)
  const [schemes, setSchemes] = useState<{ id: string; title: string }[]>([])
  useEffect(() => { api.schemes(lang).then(setSchemes).catch(() => setSchemes([])) }, [lang])

  const actions = [
    { icon: 'send', label: L('transfer'), on: () => onNav('transfer'), tone: 'bg-teal-700 text-white' },
    { icon: 'msg', label: L('check_msg'), on: () => onCheck(null), tone: 'bg-white text-slate-700' },
    { icon: 'phone', label: L('bank_calling'), on: onVerify, tone: 'bg-white text-slate-700' },
    { icon: 'help', label: L('scammed'), on: () => onNav('victim'), tone: 'bg-white text-red-600' },
  ]
  const shield = snap.shield
  const pending = snap.family_requests[0]

  // live transfers + ordinary history, newest first
  const live = snap.transfers.map(t => ({
    key: t.id, title: t.holder, amount: t.status === 'completed' ? -t.amount : -t.amount, ts: Date.now() / 1000,
    status: t.status, note: t.status === 'completed' ? null : t.title,
  }))
  const past = snap.history.map((h, i) => ({ key: `h${i}`, title: h.title, amount: h.amount, ts: h.ts, status: 'completed', note: null as string | null }))
  const ops = [...live.reverse(), ...past.sort((a, b) => b.ts - a.ts)].slice(0, 6)

  return (
    <div className="space-y-4 px-4 pb-8 pt-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-slate-200/70 font-medium text-slate-700">{snap.client.avatar}</div>
          <div>
            <div className="text-xs text-slate-500">{L('hello')},</div>
            <div className="font-medium">{snap.client.short}</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => setLargeText(!large)} aria-label={L('large_text')} title={L('large_text')}
            className={`h-8 rounded-[10px] px-2.5 text-xs font-medium ring-1 transition-colors ${large ? 'bg-slate-900 text-white ring-slate-900' : 'bg-white text-slate-700 ring-black/[0.08]'}`}>
            A<span className="text-[15px]">a</span>
          </button>
          <button onClick={onToggleLang} className="h-8 rounded-[10px] bg-white px-3 text-xs font-medium text-slate-700 ring-1 ring-black/[0.08]">
            {lang === 'kk' ? 'Қаз' : 'Рус'}
          </button>
        </div>
      </div>

      {pending && (
        <button data-tour="family-pending" onClick={() => onOpenRequest(pending.id)} className="flex w-full items-center gap-3 rounded-2xl bg-red-600 p-3 text-left text-white">
          <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/15">
            <Icon name="family" className="h-5 w-5" />
            <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-white ring-2 ring-red-600" />
          </span>
          <span className="text-sm font-medium leading-snug">{pending.headline}</span>
          <Icon name="chevron" className="ml-auto h-5 w-5 shrink-0 opacity-70" />
        </button>
      )}

      <div className="balance-card relative overflow-hidden rounded-[20px] bg-[linear-gradient(160deg,#115e59_0%,#0d4744_100%)] p-5 text-white shadow-[0_1px_2px_rgba(0,0,0,0.08),0_8px_24px_-12px_rgba(13,71,68,0.45)] ring-1 ring-inset ring-white/10">
        <div className="flex items-center justify-between text-sm text-teal-100">
          <span>{L('balance')}</span>
          <span className="flex items-center gap-1.5 text-[12px] text-teal-100/90">
            <Icon name="shield" className="h-3.5 w-3.5" />{L('qaqpan_active')}
          </span>
        </div>
        <div className="mt-2 text-[32px] font-medium leading-none tracking-tight tabular-nums">{money(snap.client.balance)}</div>
        <div className="mt-6 font-mono text-xs tracking-wider text-teal-100/70">{L('card')} •••• {CARD_TAIL[snap.client.id] ?? '0000'}</div>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {actions.map(a => (
          <button key={a.label} onClick={a.on} className="flex flex-col items-center gap-1.5 text-center">
            <span className={`grid h-14 w-14 place-items-center rounded-2xl ring-1 ring-black/[0.06] transition-transform duration-150 active:scale-95 ${a.tone}`}><Icon name={a.icon} className="h-6 w-6" /></span>
            <span className="text-[12px] leading-tight text-slate-700">{a.label}</span>
          </button>
        ))}
      </div>

      <button onClick={() => onNav('assistant')}
        className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 text-left ring-1 ring-black/[0.06] transition-[transform,background-color] duration-150 active:scale-[0.99] active:bg-slate-50">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700"><Icon name="spark" className="h-5 w-5" /></span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{L('assistant')}</span>
          <span className="block truncate text-xs text-slate-500">{L('assistant_sub')}</span>
        </span>
        <Icon name="chevron" className="h-5 w-5 shrink-0 text-slate-300" />
      </button>

      <button onClick={() => onNav('family')} className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 text-left ring-1 ring-black/[0.06] transition-[transform,background-color] duration-150 active:scale-[0.99] active:bg-slate-50">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${shield.role === 'none' ? 'bg-slate-100 text-slate-500' : 'bg-teal-50 text-teal-700'}`}>
          <Icon name="family" className="h-5 w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">
            {shield.role === 'guardian' ? `${L('you_protect')}: ${shield.wards.map(w => `${w.title} (${w.name})`).join(', ')}` : L('family_shield')}
          </span>
          <span className={`block truncate text-xs ${shield.role === 'ward' && shield.disable_at ? 'text-amber-700' : 'text-slate-500'}`}>
            {shield.role === 'ward'
              ? (shield.disable_at ? `${L('shield_off_at')} · ${shield.guardian_name}` : `${L('shield_on')} · ${shield.guardian_name} (${shield.guardian_title})`)
              : shield.role === 'guardian' ? L('guardian_sub') : L('none_sub')}
          </span>
        </span>
        <Icon name="chevron" className="h-5 w-5 shrink-0 text-slate-300" />
      </button>

      {snap.sms.length > 0 && (
        <section>
          <h3 className="mb-2 text-[13px] text-slate-500">{L('sms')}</h3>
          <div className="overflow-hidden rounded-2xl bg-white ring-1 ring-black/[0.06]">
            {snap.sms.slice().reverse().map(s => (
              <button key={s.id} data-tour="sms" onClick={() => onCheck(s.sample_id)} className="flex w-full gap-3 border-t border-slate-100 p-3 text-left first:border-0 active:bg-slate-50">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500"><Icon name="msg" className="h-4 w-4" /></span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium">{s.sender}</span>
                  <span className="line-clamp-2 block text-xs text-slate-600">{s.text}</span>
                  <span className="mt-1 block text-[12px] font-medium text-teal-700">{L('tap_to_check')}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-[13px] text-slate-500">{L('operations')}</h3>
        <div className="overflow-hidden rounded-2xl bg-white ring-1 ring-black/[0.06]">
          {ops.map(o => {
            const paused = o.status !== 'completed'
            const cancelled = o.status === 'cancelled'
            return (
              <div key={o.key} className="flex items-center gap-3 border-t border-slate-100 px-3 py-2.5 first:border-0">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-medium ${cancelled ? 'bg-teal-50 text-teal-700' : paused ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>
                  {cancelled ? <Icon name="shield" className="h-4 w-4" /> : o.amount > 0 ? '+' : paused ? '!' : '−'}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm">{o.title}</span>
                  <span className={`block truncate text-xs ${cancelled ? 'text-teal-700' : paused ? 'text-amber-700' : 'text-slate-400'}`}>
                    {o.note ?? when(o.ts, lang)}
                  </span>
                </span>
                <span className={`shrink-0 text-sm font-medium tabular-nums ${o.amount > 0 ? 'text-emerald-700' : cancelled ? 'text-slate-400 line-through' : paused ? 'text-amber-700' : 'text-slate-900'}`}>
                  {o.amount > 0 ? '+' : '−'}{money(Math.abs(o.amount))}
                </span>
              </div>
            )
          })}
        </div>
      </section>

      {schemes.length > 0 && (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-500">{L('new_schemes')}</h3>
            <button onClick={() => onNav('schemes')} className="text-xs font-semibold text-teal-700">›</button>
          </div>
          <div className="relative -mx-4">
            <div className="flex snap-x gap-2 overflow-x-auto px-4 pb-1">
              {schemes.map(s => (
                <button key={s.id} onClick={() => onNav('schemes')} className="w-40 shrink-0 snap-start rounded-2xl bg-amber-50 p-3 text-left ring-1 ring-amber-100">
                  <Icon name="news" className="h-5 w-5 text-amber-600" />
                  <div className="mt-2 line-clamp-3 text-xs font-semibold leading-snug text-amber-900">{s.title}</div>
                </button>
              ))}
            </div>
            <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-slate-50" />
          </div>
        </section>
      )}
    </div>
  )
}
