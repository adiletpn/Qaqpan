import { useState } from 'react'
import { api } from '../api'
import { StepsBar } from './Stage'
import { ACTIONS, useDirectorHotkeys, useStage } from './shared'

export default function Director() {
  const { stage, offline } = useStage(700)
  const [err, setErr] = useState<string | null>(null)
  const [last, setLast] = useState<string | null>(null)
  useDirectorHotkeys(setErr)
  const run = async (action: string) => {
    setLast(action); setErr(null)
    try { await api.director(action) } catch (e) { setErr(e instanceof Error ? e.message : 'Ошибка') }
  }
  return (
    <div className="min-h-screen bg-slate-950 p-6 text-white">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-black">Пульт демо</h1>
          <div className="text-right"><span className="text-3xl font-black text-emerald-400">{stage?.stopped ?? 0}</span> <span className="text-sm text-slate-400">остановлено</span></div>
        </div>
        {(offline || err) && (
          <div className="mt-3 rounded-xl bg-amber-500/20 px-4 py-2 text-sm text-amber-200 ring-1 ring-amber-500/40">
            {offline ? 'Нет связи с сервером — повторяем…' : err}{err?.includes('ключ') ? ' — откройте /director?key=…' : ''}
          </div>
        )}
        <div className="mt-4 overflow-x-auto"><StepsBar fired={stage?.steps ?? []} /></div>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {ACTIONS.map(a => (
            <button key={a.action} onClick={() => run(a.action)}
              className={`flex items-start gap-4 rounded-2xl p-4 text-left ring-1 transition active:scale-[.98] ${a.action === 'reset' ? 'bg-red-950/60 ring-red-800' : last === a.action ? 'bg-emerald-900/50 ring-emerald-600' : 'bg-white/5 ring-white/10 hover:bg-white/10'}`}>
              <kbd className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10 font-mono text-lg font-bold">{a.key}</kbd>
              <div>
                <div className="font-semibold">{a.title}</div>
                {a.hint && <div className="mt-0.5 text-sm text-slate-400">{a.hint}</div>}
              </div>
            </button>
          ))}
        </div>
        <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-slate-500">Лента событий</h2>
        <div className="mt-2 space-y-1 font-mono text-sm">
          {(stage?.events ?? []).slice().reverse().map(e => (
            <div key={e.seq} className={e.stopped ? 'text-emerald-400' : 'text-slate-300'}>#{e.seq} {e.text}</div>
          ))}
        </div>
      </div>
    </div>
  )
}
