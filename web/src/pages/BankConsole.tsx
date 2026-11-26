import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState, type ReactNode } from 'react'
import { api, money, type BankConsoleData, type BankItem, type DropProfile } from '../api'
import { Icon } from '../ui'

// The bank's side of Qaqpan: the antifraud analyst's workstation. Quiet graphite chrome, one teal accent,
// red only for «block» and «drop». The one rich moment is the money-flow sketch of the drop account.
// Staff view: the client never sees anything about another person's account.

const EASE = [0.22, 1, 0.36, 1] as const
const STATUS: Record<string, { label: string; dot: string }> = {
  held: { label: 'Остановлен', dot: 'bg-red-600' },
  escalated: { label: 'Семья не ответила', dot: 'bg-amber-500' },
  delayed: { label: 'Отложен на час', dot: 'bg-neutral-400' },
  awaiting_family: { label: 'Ждёт сына', dot: 'bg-teal-700' },
  cancelled: { label: 'Деньги спасены', dot: 'bg-green-600' },
  completed: { label: 'Проведён', dot: 'bg-neutral-300' },
}
const FAMILY: Record<string, string> = { pending: 'ждёт ответа сына', declined: 'сын отклонил', approved: 'сын разрешил', expired: 'сын не ответил за 15 мин', withdrawn: 'запрос отозван' }
const DELAY: Record<string, string> = { likely_scam: 'похоже на обман', unclear: 'есть сомнения', likely_ok: 'признаков нет' }
const bankName = (b: string) => (b === 'BCC' ? 'наш банк' : b)
const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
const pct = (s: number) => Math.round(s * 100)

// «KZ86 8562 0000 0471 1934» -> «KZ86 •••• 1934»: the analyst needs the ends, not the whole number on a projector
function masked(display: string) {
  const parts = display.split(' ')
  return parts.length > 2 ? `${parts[0]} •••• ${parts[parts.length - 1]}` : display
}

export function BankConsole({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<BankConsoleData | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [updated, setUpdated] = useState<number | null>(null)
  useEffect(() => {
    let alive = true
    const run = () => api.bankConsole().then(d => { if (alive) { setData(d); setUpdated(Date.now() / 1000) } }).catch(() => undefined)
    run()
    const t = setInterval(run, 1500)
    return () => { alive = false; clearInterval(t) }
  }, [])
  const all = [...(data?.queue ?? []), ...(data?.history ?? [])]
  const current = all.find(i => i.id === sel) ?? data?.queue[0] ?? data?.history[0] ?? null
  const decide = async (id: string, action: 'release' | 'block') => {
    setBusy(id)
    try { await api.bankDecision(id, action); setData(await api.bankConsole()) } catch { /* the next poll shows the state */ } finally { setBusy(null) }
  }
  const [lead, ...watch] = data?.drops ?? []

  return (
    <div className={`h-full w-full overflow-y-auto overflow-x-hidden bg-[#fafafa] text-[#171717] ${compact ? 'px-4 py-4' : 'px-4 py-4 sm:px-8 sm:py-6'}`}>
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className={`font-medium leading-tight ${compact ? 'text-[20px]' : 'text-[20px] sm:text-[24px]'}`}>Антифрод-консоль</h1>
          <p className="mt-1 text-[13px] text-[#525252]">Рабочее место аналитика · решение остаётся за банком</p>
        </div>
        <p className="flex shrink-0 items-center gap-2 pt-1 text-[12px] text-[#737373]">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-700" />
          <span className="font-mono tabular-nums">{updated ? time(updated) : '—'}</span>
        </p>
      </header>

      <section className={`mt-5 grid gap-px overflow-hidden rounded-2xl border border-black/[0.08] bg-black/[0.08] ${compact ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-4'}`}>
        <Stat label="Спасено" value={money(data?.stats.saved ?? 0)} accent />
        <Stat label="Остановлено попыток" value={String(data?.stats.stopped ?? 0)} />
        <Stat label="В очереди" value={String(data?.stats.queue ?? 0)} />
        <Stat label="Дроп-счетов" value={String(data?.stats.drops ?? 0)} danger={!!data?.stats.drops} />
      </section>

      <div className={`mt-6 grid gap-6 ${compact ? '' : 'lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start'}`}>
        <div className="min-w-0 space-y-6">
          <Block title="Подозрительные счета" meta={data ? String(data.drops.length) : ''}>
            {data && !lead && <Empty text="Детектор пока ничего не нашёл" />}
            {lead && <Dossier d={lead} compact={compact} />}
            {watch.length > 0 && (
              <div className="mt-2 divide-y divide-black/[0.06] overflow-hidden rounded-xl border border-black/[0.08] bg-white">
                {watch.map(d => <WatchRow key={d.account} d={d} />)}
              </div>
            )}
          </Block>

          <Block title="Очередь" meta={data ? String(data.queue.length) : ''}>
            {data && data.queue.length === 0 && <Empty text="Очередь пуста" />}
            <div className="space-y-1">
              {data?.queue.map(i => <Row key={i.id} i={i} on={current?.id === i.id} onClick={() => setSel(i.id)} />)}
            </div>
            {data && data.history.length > 0 && (
              <>
                <p className="mb-2 mt-5 text-[12px] text-[#737373]">Решено</p>
                <div className="space-y-1">
                  {data.history.map(i => <Row key={i.id} i={i} on={current?.id === i.id} onClick={() => setSel(i.id)} />)}
                </div>
              </>
            )}
          </Block>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {current && (
            <motion.section key={current.id} className="min-w-0" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }} transition={{ duration: 0.2, ease: EASE }}>
              <div className="mb-3 flex items-baseline gap-2">
                <h2 className="text-[15px] font-medium">Операция</h2>
                <span className="font-mono text-[12px] text-[#737373]">{time(current.ts)}</span>
              </div>
              <Detail i={current} busy={busy === current.id} onDecide={decide} />
            </motion.section>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function Kpi({ label, value, tone = '' }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200/70">
      <div className={`text-xl font-black tabular-nums ${tone}`}>{value}</div>
      <div className="text-[11px] text-slate-500">{label}</div>
    </div>
  )
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2 px-1"><span className="text-sm font-bold">{title}</span><span className="truncate text-[11px] text-slate-400">{hint}</span></div>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

const Empty = ({ text }: { text: string }) => <div className="rounded-2xl bg-white/60 p-4 text-center text-sm text-slate-400 ring-1 ring-slate-200/70">{text}</div>

function DropCard({ d }: { d: DropProfile }) {
  const drop = d.label === 'drop'
  return (
    <motion.div layout data-tour="drop-card" className={`rounded-2xl bg-white p-3 shadow-sm ring-1 ${drop ? 'ring-red-200' : 'ring-amber-200'}`}>
      <div className="flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${drop ? 'bg-red-600 text-white' : 'bg-amber-100 text-amber-900'}`}>{drop ? 'Вероятный дроп' : 'Под наблюдением'}</span>
        <span className="truncate font-mono text-xs text-slate-500">{d.display}</span>
        <span className="ml-auto text-sm font-black tabular-nums">{Math.round(d.score * 100)}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <motion.div className={`h-full rounded-full ${drop ? 'bg-red-500' : 'bg-amber-400'}`} initial={{ width: 0 }} animate={{ width: `${d.score * 100}%` }} transition={{ duration: 0.6, ease: EASE }} />
      </div>
      <div className="mt-2 text-xs text-slate-600">{d.holder} · {bankName(d.bank)}{d.attempts > 0 && <> · входящие за сутки: <b>{money(d.inflow)}</b> от {d.senders} клиент{d.senders === 1 ? 'а' : 'ов'}</>}</div>
      <ul className="mt-1.5 space-y-0.5 text-xs text-slate-500">{d.signals.map(s => <li key={s}>• {s}</li>)}</ul>
    </motion.div>
  )
}

function Row({ i, on, onClick }: { i: BankItem; on: boolean; onClick: () => void }) {
  const st = STATUS[i.status] ?? { label: i.status, tone: 'bg-slate-100' }
  return (
    <button onClick={onClick} className={`flex w-full items-center gap-3 rounded-2xl bg-white p-3 text-left shadow-sm ring-1 transition ${on ? 'ring-2 ring-slate-900' : 'ring-slate-200/70 hover:ring-slate-300'}`}>
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl text-xs font-black ${i.score >= 0.5 ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>{Math.round(i.score * 100)}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">{i.client.name} · {money(i.amount)}</span>
        <span className="block truncate text-xs text-slate-500">{time(i.ts)} → {i.recipient.display}</span>
      </span>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.tone}`}>{st.label}</span>
    </button>
  )
}

function Detail({ i, busy, onDecide }: { i: BankItem; busy: boolean; onDecide: (id: string, a: 'release' | 'block') => void }) {
  const st = STATUS[i.status] ?? { label: i.status, tone: 'bg-slate-100' }
  const active = ['held', 'escalated', 'delayed', 'awaiting_family'].includes(i.status)
  return (
    <div className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200/70" data-tour="bank-detail">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-slate-500">{i.client.name}, {i.client.age} лет · {i.client.city}</div>
          <div className="text-2xl font-black tabular-nums">{money(i.amount)}</div>
          <div className="truncate text-sm text-slate-600">→ {i.recipient.display} · {i.recipient.holder} · {bankName(i.recipient.bank)}</div>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${st.tone}`}>{st.label}</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip tone="bg-slate-900 text-white">риск {Math.round(i.score * 100)}</Chip>
        {i.unusual_x && i.unusual_x >= 5 && <Chip tone="bg-violet-100 text-violet-900">в {i.unusual_x} раз больше обычных трат</Chip>}
        {i.drop.label === 'drop' && <Chip tone="bg-red-100 text-red-800">получатель — вероятный дроп</Chip>}
        {i.family && <Chip tone="bg-teal-100 text-teal-900">{FAMILY[i.family] ?? i.family}</Chip>}
        {i.delay && <Chip tone="bg-sky-100 text-sky-900">вывод за час: {DELAY[i.delay] ?? i.delay}</Chip>}
        {i.decided_by_bank && <Chip tone="bg-slate-100 text-slate-700">решение аналитика: {i.decided_by_bank === 'block' ? 'заблокирован' : 'разрешён'}</Chip>}
      </div>

      <div className="mt-4 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 p-3 ring-1 ring-emerald-100" data-tour="bank-note">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-emerald-800">
          <span className="rounded bg-emerald-700 px-1.5 py-0.5 text-[10px] text-white">ИИ</span>сводка для аналитика
          <span className="ml-auto font-normal normal-case text-emerald-700/70">{i.note.source === 'rules' ? 'по правилам' : 'Mistral'}</span>
        </div>
        <p className="text-sm leading-relaxed text-slate-800">{i.note.text}</p>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">Причины</div>
          <ul className="space-y-1 text-sm text-slate-700">{i.reasons.map(r => <li key={r}>• {r}</li>)}</ul>
        </div>
        <div>
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">Сессия клиента</div>
          <ol className="space-y-1.5 border-l-2 border-slate-200 pl-3 text-sm">
            {i.timeline.length === 0 && <li className="text-slate-400">событий нет</li>}
            {i.timeline.map((e, k) => <li key={k} className="text-slate-700"><span className="mr-1.5 font-mono text-[11px] text-slate-400">{time(e.ts)}</span>{e.text}</li>)}
          </ol>
        </div>
      </div>

      {active && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button disabled={busy} onClick={() => onDecide(i.id, 'block')} className="rounded-2xl bg-red-600 py-3 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50">Заблокировать</button>
          <button disabled={busy} onClick={() => onDecide(i.id, 'release')} className="rounded-2xl bg-white py-3 text-sm font-semibold text-slate-800 ring-1 ring-slate-200 transition active:scale-[0.98] disabled:opacity-50">Разрешить</button>
        </div>
      )}
    </div>
  )
}

const Chip = ({ tone, children }: { tone: string; children: React.ReactNode }) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{children}</span>

export default function BankPage() {
  return <div className="h-[100dvh]"><BankConsole /></div>
}
