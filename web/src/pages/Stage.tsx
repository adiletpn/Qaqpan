import { useEffect, useState } from 'react'
import { money } from '../api'
import BankApp from '../phone/BankApp'
import { Icon } from '../ui'
import { setTheme, useTheme } from '../theme'
import { ACTIONS, STEPS, useDirectorHotkeys, useStage } from './shared'

const PHONES = [
  { id: 'aigerim', caption: 'Айгерим, 52', role: 'клиентка банка' },
  { id: 'erzhan', caption: 'Ержан, 27', role: 'сын · доверенное лицо' },
  { id: 'madina', caption: 'Мадина, 34', role: 'другая клиентка' },
]

const PHONE_W = 390, PHONE_H = 820, GAP = 40

function useViewport() {
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight })
  useEffect(() => {
    const h = () => setVp({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  }, [])
  return vp
}

// fit three phones into the viewport by height AND width (projector 1920×1080 down to laptop 1366×768)
function phoneScale(w: number, h: number) {
  const byHeight = (h - 252) / PHONE_H  // header + captions + the event feed
  const byWidth = (w - 48 - 2 * GAP) / (3 * PHONE_W)
  return Math.min(1, Math.max(0.4, Math.min(byHeight, byWidth)))
}

export function PhoneFrame({ clientId, scale = 1 }: { clientId: string; scale?: number }) {
  const W = PHONE_W, H = PHONE_H
  return (
    <div style={{ width: W * scale, height: H * scale }}>
      <div style={{ width: W, height: H, transform: `scale(${scale})`, transformOrigin: 'top left' }}
        className="overflow-hidden rounded-[48px] border-[10px] border-slate-900 bg-slate-900 shadow-2xl ring-1 ring-white/10">
        <div className="relative h-full overflow-hidden rounded-[38px] bg-slate-50">
          <div className="flex h-7 items-center justify-between bg-slate-50 px-7 text-[11px] font-semibold text-slate-800">
            <span>9:41</span><span className="h-4 w-20 rounded-full bg-slate-900" /><span>LTE</span>
          </div>
          <div className="h-[calc(100%-1.75rem)]"><BankApp clientId={clientId} /></div>
        </div>
      </div>
    </div>
  )
}

export function StepsBar({ fired, compact = false }: { fired: string[]; compact?: boolean }) {
  return (
    <div className="flex items-stretch gap-1.5">
      {STEPS.map((s, i) => {
        const on = fired.includes(s.id)
        return (
          <div key={s.id} className="flex items-center gap-1.5">
            <div className={`rounded-2xl transition-all duration-500 ${compact ? 'px-3 py-2' : 'min-w-44 px-4 py-2.5'} ${on ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30' : 'bg-white/5 text-slate-300 ring-1 ring-white/10'}`}>
              <div className={`flex items-center gap-2 whitespace-nowrap font-bold ${compact ? 'text-xs' : 'text-sm'}`}>
                <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] ${on ? 'bg-white text-emerald-600' : 'bg-white/10'}`}>{on ? '✓' : s.n}</span>
                {s.title}
              </div>
              <div className={`mt-0.5 whitespace-nowrap text-[11px] ${on ? 'text-emerald-50' : 'text-slate-500'}`}>{on ? 'остановлено' : s.layer}</div>
            </div>
            {i < STEPS.length - 1 && <span className="text-slate-600">›</span>}
          </div>
        )
      })}
    </div>
  )
}

export default function Stage() {
  const { stage, offline } = useStage()
  const [warn, setWarn] = useState<string | null>(null)
  const vp = useViewport()
  const scale = phoneScale(vp.w, vp.h)
  const compact = vp.w < 1600
  useDirectorHotkeys(setWarn)
  useEffect(() => { if (!warn) return; const t = setTimeout(() => setWarn(null), 4000); return () => clearTimeout(t) }, [warn])
  const [help, setHelp] = useState(false)
  const theme = useTheme()
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return
      if (e.key === '?' || e.code === 'KeyH') setHelp(v => !v)
      if (e.code === 'KeyT' && !e.metaKey && !e.ctrlKey) setTheme(theme === 'bcc' ? 'default' : 'bcc')
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [theme])
  const events = (stage?.events ?? []).filter(e => e.kind !== 'reset').slice(-3).reverse()
  if (vp.w < 900) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-950 p-6 text-center text-white">
        <div>
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-500"><Icon name="shield" className="h-7 w-7" /></div>
          <h1 className="mt-4 text-2xl font-black">Сцена — для большого экрана</h1>
          <p className="mt-2 text-sm text-slate-400">На телефоне откройте само приложение:</p>
          <div className="mt-4 grid gap-2">
            {PHONES.map(p => <a key={p.id} href={`/phone/${p.id}`} className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/10">{p.caption} · {p.role}</a>)}
          </div>
        </div>
      </div>
    )
  }
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-950 px-6 py-4 text-white">
      <header className="flex items-center justify-between gap-4">
        <div className="flex shrink-0 items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-500"><Icon name="shield" className="h-6 w-6" /></div>
          <div>
            <div className="text-2xl font-black tracking-tight">Qaqpan</div>
            <div className={`text-xs text-slate-400 ${compact ? 'max-w-40' : ''}`}>капкан для мошенников внутри приложения банка</div>
          </div>
        </div>
        <StepsBar fired={stage?.steps ?? []} compact={compact} />
        <div className="shrink-0 text-right">
          <div className="text-4xl font-black tabular-nums text-emerald-400">{money(stage?.saved ?? 0)}</div>
          <div className="text-xs text-slate-400">спасено · остановлено попыток: {stage?.stopped ?? 0}</div>
        </div>
      </header>

      <main className="mt-4 flex min-h-0 flex-1 items-start justify-center" style={{ gap: GAP }}>
        {PHONES.map(p => (
          <div key={p.id} className="flex flex-col items-center">
            <PhoneFrame clientId={p.id} scale={scale} />
            <div className="mt-2 text-center">
              <div className="font-bold leading-tight">{p.caption}</div>
              <div className="text-xs text-slate-400">{p.role}</div>
            </div>
          </div>
        ))}
      </main>

      {(offline || warn) && (
        <div className="fixed left-1/2 top-24 z-50 -translate-x-1/2 rounded-full bg-amber-500 px-4 py-1.5 text-sm font-semibold text-white shadow-lg">
          {offline ? 'Нет связи с сервером — повторяем…' : warn}
        </div>
      )}

      {help && (
        <div className="fixed bottom-6 right-6 z-50 w-96 rounded-2xl bg-slate-900/95 p-4 text-sm shadow-2xl ring-1 ring-white/10">
          <div className="mb-2 font-bold">Горячие клавиши · H — скрыть</div>
          {ACTIONS.map(a => (
            <div key={a.key} className="flex gap-3 py-0.5"><kbd className="w-6 text-center font-mono text-emerald-400">{a.key}</kbd><span className="text-slate-300">{a.title}</span></div>
          ))}
          <div className="flex gap-3 py-0.5"><kbd className="w-6 text-center font-mono text-emerald-400">T</kbd><span className="text-slate-300">Стиль BCC / свой стиль телефонов</span></div>
        </div>
      )}

      <footer className="mt-2 flex h-[84px] shrink-0 flex-col-reverse justify-start gap-0.5 overflow-hidden text-base">
        {events.map((e, i) => (
          <div key={e.seq} className={`flex min-w-0 items-center gap-2 transition-opacity ${i === 0 ? 'text-white' : 'text-slate-500'}`}>
            <span className={`h-2 w-2 shrink-0 rounded-full ${e.stopped ? 'bg-emerald-400' : 'bg-slate-500'}`} /><span className="truncate">{e.text}</span>
          </div>
        ))}
      </footer>
    </div>
  )
}
