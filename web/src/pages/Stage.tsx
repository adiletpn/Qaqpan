import { useEffect, useState } from 'react'
import BankApp from '../phone/BankApp'
import { Icon } from '../ui'
import { STEPS, useDirectorHotkeys, useStage } from './shared'

const PHONES = [
  { id: 'aigerim', caption: 'Айгерим, 52', role: 'клиентка банка' },
  { id: 'erzhan', caption: 'Ержан, 27', role: 'сын · доверенное лицо' },
  { id: 'madina', caption: 'Мадина, 34', role: 'другая клиентка' },
]

function useScale(designH: number, reserved: number) {
  const calc = () => Math.min(1, Math.max(0.45, (window.innerHeight - reserved) / designH))
  const [scale, setScale] = useState(calc)
  useEffect(() => {
    const h = () => setScale(calc())
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  })
  return scale
}

export function PhoneFrame({ clientId, scale = 1 }: { clientId: string; scale?: number }) {
  const W = 390, H = 820
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

export function StepsBar({ fired }: { fired: string[] }) {
  return (
    <div className="flex items-stretch gap-2">
      {STEPS.map((s, i) => {
        const on = fired.includes(s.id)
        return (
          <div key={s.id} className="flex items-center gap-2">
            <div className={`min-w-44 rounded-2xl px-4 py-2.5 transition-all duration-500 ${on ? 'scale-105 bg-emerald-500 text-white shadow-lg shadow-emerald-500/30' : 'bg-white/5 text-slate-300 ring-1 ring-white/10'}`}>
              <div className="flex items-center gap-2 text-sm font-bold">
                <span className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${on ? 'bg-white text-emerald-600' : 'bg-white/10'}`}>{on ? '✓' : s.n}</span>
                {s.title}
              </div>
              <div className={`mt-0.5 text-[11px] ${on ? 'text-emerald-50' : 'text-slate-500'}`}>{on ? 'остановлено · ' : ''}{s.layer}</div>
            </div>
            {i < STEPS.length - 1 && <span className="text-slate-600">→</span>}
          </div>
        )
      })}
    </div>
  )
}

export default function Stage() {
  const stage = useStage()
  const scale = useScale(820, 250)
  useDirectorHotkeys()
  const events = (stage?.events ?? []).filter(e => e.kind !== 'reset').slice(-4).reverse()
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 px-6 py-4 text-white">
      <header className="flex items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-500"><Icon name="shield" className="h-6 w-6" /></div>
          <div>
            <div className="text-2xl font-black tracking-tight">Qalqan</div>
            <div className="text-xs text-slate-400">щит от мошенников внутри приложения банка</div>
          </div>
        </div>
        <StepsBar fired={stage?.steps ?? []} />
        <div className="text-right">
          <div className="text-4xl font-black tabular-nums text-emerald-400">{stage?.stopped ?? 0}</div>
          <div className="text-xs text-slate-400">попыток остановлено</div>
        </div>
      </header>

      <main className="mt-5 flex flex-1 items-start justify-center gap-10">
        {PHONES.map(p => (
          <div key={p.id} className="flex flex-col items-center">
            <PhoneFrame clientId={p.id} scale={scale} />
            <div className="mt-3 text-center">
              <div className="font-bold">{p.caption}</div>
              <div className="text-xs text-slate-400">{p.role}</div>
            </div>
          </div>
        ))}
      </main>

      <footer className="mt-3 flex h-16 flex-col-reverse justify-start gap-1 overflow-hidden text-sm">
        {events.map((e, i) => (
          <div key={e.seq} className={`flex items-center gap-2 transition-opacity ${i === 0 ? 'text-white' : 'text-slate-500'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${e.stopped ? 'bg-emerald-400' : 'bg-slate-500'}`} />{e.text}
          </div>
        ))}
      </footer>
    </div>
  )
}
