import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api, money, type BankConsoleData, type BankItem, type DropProfile } from '../api'
import { EASE } from '../motion'
import { Icon } from '../ui'

// The bank's side of Qaqpan: what an antifraud analyst sees. Qaqpan complements the bank's antifraud —
// the decision stays with the bank. Staff view: the client never sees anything about another person's account.
const STATUS: Record<string, { label: string; tone: string }> = {
  held: { label: 'Остановлен', tone: 'bg-red-100 text-red-800' },
  escalated: { label: 'Семья не ответила', tone: 'bg-amber-100 text-amber-900' },
  delayed: { label: 'Отложен на час', tone: 'bg-sky-100 text-sky-900' },
  awaiting_family: { label: 'Ждёт семью', tone: 'bg-teal-100 text-teal-900' },
  cancelled: { label: 'Деньги спасены', tone: 'bg-emerald-100 text-emerald-800' },
  completed: { label: 'Проведён', tone: 'bg-slate-100 text-slate-700' },
}
const FAMILY: Record<string, string> = { pending: 'ждёт ответа сына', declined: 'сын отклонил', approved: 'сын разрешил', expired: 'сын не ответил за 15 мин', withdrawn: 'запрос отозван' }
const DELAY: Record<string, string> = { likely_scam: 'похоже на обман', unclear: 'есть сомнения', likely_ok: 'признаков нет' }
const bankName = (b: string) => (b === 'BCC' ? 'наш банк' : b)
const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

export function BankConsole({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<BankConsoleData | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    const run = () => api.bankConsole().then(d => { if (alive) setData(d) }).catch(() => undefined)
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

  return (
    <div className={`h-full w-full overflow-y-auto overflow-x-hidden bg-slate-100 text-slate-900 ${compact ? 'p-3' : 'p-5 md:p-6'}`}>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-2xl bg-slate-900 text-white"><Icon name="shield" className="h-5 w-5" /></span>
        <div className="min-w-0">
          <div className="font-black leading-tight">Антифрод-консоль банка</div>
          <div className="text-xs text-slate-500">рабочее место аналитика · решение остаётся за банком</div>
        </div>
        <span className="ml-auto flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />онлайн
        </span>
      </div>

      <div className={`mt-4 grid gap-2 ${compact ? 'grid-cols-2' : 'grid-cols-2 md:grid-cols-4'}`}>
        <Kpi label="Спасено" value={money(data?.stats.saved ?? 0)} tone="text-emerald-600" />
        <Kpi label="Остановлено попыток" value={String(data?.stats.stopped ?? 0)} />
        <Kpi label="В очереди аналитика" value={String(data?.stats.queue ?? 0)} tone={data?.stats.queue ? 'text-amber-600' : ''} />
        <Kpi label="Дроп-счетов" value={String(data?.stats.drops ?? 0)} tone={data?.stats.drops ? 'text-red-600' : ''} />
      </div>

      <div className={`mt-4 grid gap-4 ${compact ? '' : 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]'}`}>
        <div className="min-w-0 space-y-4">
          <Section title="Подозрительные счета" hint="детектор дропов: деньги от разных клиентов, жалобы, новый счёт">
            {data && data.drops.length === 0 && <Empty text="Подозрительных счетов пока нет" />}
            {data?.drops.map(d => <DropCard key={d.account} d={d} />)}
          </Section>
          <Section title="Очередь" hint="остановленные и отложенные переводы">
            {data && data.queue.length === 0 && <Empty text="Очередь пуста" />}
            {data?.queue.map(i => <Row key={i.id} i={i} on={current?.id === i.id} onClick={() => setSel(i.id)} />)}
            {data && data.history.length > 0 && <div className="px-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Решено</div>}
            {data?.history.map(i => <Row key={i.id} i={i} on={current?.id === i.id} onClick={() => setSel(i.id)} />)}
          </Section>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          {current && (
            <motion.div key={current.id} className="min-w-0" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.22, ease: EASE }}>
              <Detail i={current} busy={busy === current.id} onDecide={decide} />
            </motion.div>
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
