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

// hairlines come from the 1px gap over a tinted grid, so the 2×2 and 1×4 layouts both draw clean dividers
function Stat({ label, value, accent, danger }: { label: string; value: string; accent?: boolean; danger?: boolean }) {
  return (
    <div className="min-w-0 bg-white px-4 py-4">
      <p className="truncate text-[12px] text-[#737373]">{label}</p>
      <p className={`mt-2 truncate text-[20px] font-medium leading-none tabular-nums sm:text-[24px] ${accent ? 'text-teal-700' : danger ? 'text-red-600' : ''}`}>{value}</p>
    </div>
  )
}

function Block({ title, meta, children }: { title: string; meta?: string; children: ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="text-[15px] font-medium">{title}</h2>
        {meta && <span className="font-mono text-[12px] text-[#737373]">{meta}</span>}
      </div>
      {children}
    </section>
  )
}

const Empty = ({ text }: { text: string }) => (
  <div className="rounded-xl border border-dashed border-black/[0.12] px-4 py-6 text-center text-[13px] text-[#737373]">{text}</div>
)

// The moment of the screen: where the money comes from, drawn as a flow into one account
function Dossier({ d, compact }: { d: DropProfile; compact: boolean }) {
  const flows = d.flows ?? []
  const drop = d.label === 'drop'
  const rowH = 44
  const h = Math.max(1, flows.length) * rowH
  return (
    <div data-tour="drop-card" className="rounded-2xl border border-black/[0.08] bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <p className={`flex items-center gap-2 text-[13px] font-medium ${drop ? 'text-red-600' : 'text-amber-700'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${drop ? 'bg-red-600' : 'bg-amber-500'}`} />
          {drop ? 'Вероятный дроп' : 'Под наблюдением'}
        </p>
        <p className="font-mono text-[13px] tabular-nums text-[#525252]"><span className="text-[#171717]">{pct(d.score)}</span>/100</p>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/[0.06]">
        <div className={`h-full rounded-full ${drop ? 'bg-red-600' : 'bg-amber-500'}`} style={{ width: `${pct(d.score)}%` }} />
      </div>

      {flows.length > 0 ? (
        <div className={`mt-5 grid items-center ${compact ? 'grid-cols-[minmax(0,1fr)_32px_minmax(0,1.3fr)]' : 'grid-cols-[minmax(0,1fr)_32px_minmax(0,1.3fr)] sm:grid-cols-[minmax(0,1fr)_64px_minmax(0,1fr)]'}`}>
          <div>
            {flows.map(f => (
              <div key={f.name} className="flex h-11 flex-col justify-center">
                <p className="truncate text-[13px] text-[#525252]">{f.name}</p>
                <p className="font-mono text-[14px] tabular-nums">{money(f.amount)}</p>
              </div>
            ))}
          </div>
          <svg viewBox={`0 0 64 ${h}`} preserveAspectRatio="none" className="w-full" style={{ height: h }} aria-hidden>
            {flows.map((_, k) => {
              const y = k * rowH + rowH / 2
              return <path key={k} d={`M0 ${y} C 32 ${y}, 32 ${h / 2}, 60 ${h / 2}`} fill="none" stroke={drop ? '#dc2626' : '#d97706'}
                strokeOpacity="0.55" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            })}
            <circle cx="61" cy={h / 2} r="2.5" fill={drop ? '#dc2626' : '#d97706'} />
          </svg>
          <div className="min-w-0 rounded-xl bg-[#f4f4f5] px-3 py-3">
            <p className="truncate font-mono text-[13px] tabular-nums">{masked(d.display)}</p>
            <p className="mt-1 truncate text-[12px] text-[#737373]">{d.holder} · {bankName(d.bank)}</p>
            <p className="mt-2 truncate font-mono text-[13px] tabular-nums text-red-600">{money(d.inflow)}</p>
            <p className="text-[12px] text-[#737373]">за сутки от {d.senders} клиент{d.senders === 1 ? 'а' : 'ов'}</p>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <p className="font-mono text-[14px] tabular-nums">{masked(d.display)}</p>
          <p className="mt-1 text-[12px] text-[#737373]">{d.holder} · {bankName(d.bank)}</p>
        </div>
      )}

      <ul className="mt-4 space-y-1 border-t border-black/[0.06] pt-3 text-[13px] text-[#525252]">
        {d.signals.map(s => <li key={s}>{s}</li>)}
      </ul>
    </div>
  )
}

function WatchRow({ d }: { d: DropProfile }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${d.label === 'drop' ? 'bg-red-600' : 'bg-amber-500'}`} />
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[13px] tabular-nums">{masked(d.display)}</p>
        <p className="truncate text-[12px] text-[#737373]">{d.signals[0] ?? d.holder}</p>
      </div>
      <p className="font-mono text-[13px] tabular-nums text-[#525252]">{pct(d.score)}</p>
    </div>
  )
}

function Row({ i, on, onClick }: { i: BankItem; on: boolean; onClick: () => void }) {
  const st = STATUS[i.status] ?? { label: i.status, dot: 'bg-neutral-300' }
  return (
    <button onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition-colors duration-150 ${on
        ? 'border-black/[0.08] bg-white shadow-[0_1px_2px_rgba(0,0,0,0.05)]' : 'border-transparent hover:bg-black/[0.03]'}`}>
      <span className={`w-8 shrink-0 font-mono text-[13px] tabular-nums ${i.score >= 0.5 ? 'text-red-600' : 'text-[#525252]'}`}>{pct(i.score)}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px]">{i.client.name}</span>
        <span className="block truncate font-mono text-[12px] tabular-nums text-[#737373]">{time(i.ts)} · {masked(i.recipient.display)}</span>
      </span>
      <span className="shrink-0 text-right">
        <span className="block font-mono text-[14px] tabular-nums">{money(i.amount)}</span>
        <span className="flex items-center justify-end gap-1.5 text-[12px] text-[#525252]"><span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />{st.label}</span>
      </span>
    </button>
  )
}

function Detail({ i, busy, onDecide }: { i: BankItem; busy: boolean; onDecide: (id: string, a: 'release' | 'block') => void }) {
  const st = STATUS[i.status] ?? { label: i.status, dot: 'bg-neutral-300' }
  const active = ['held', 'escalated', 'delayed', 'awaiting_family'].includes(i.status)
  const facts: [string, string, boolean?][] = [
    ['Риск', `${pct(i.score)}/100`, i.score >= 0.5],
    ...(i.unusual_x && i.unusual_x >= 5 ? [['Норма клиента', `в ${i.unusual_x} раз больше обычных трат`] as [string, string]] : []),
    ...(i.drop.label === 'drop' ? [['Получатель', 'вероятный дроп', true] as [string, string, boolean]] : []),
    ...(i.family ? [['Семья', FAMILY[i.family] ?? i.family] as [string, string]] : []),
    ...(i.delay ? [['Вывод за час', DELAY[i.delay] ?? i.delay, i.delay === 'likely_scam'] as [string, string, boolean]] : []),
    ...(i.decided_by_bank ? [['Решение аналитика', i.decided_by_bank === 'block' ? 'заблокирован' : 'разрешён'] as [string, string]] : []),
  ]
  return (
    <div data-tour="bank-detail" className="rounded-2xl border border-black/[0.08] bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[13px] text-[#525252]">{i.client.name}, {i.client.age} лет · {i.client.city}</p>
          <p className="mt-2 text-[28px] font-medium leading-none tabular-nums sm:text-[32px]">{money(i.amount)}</p>
          <p className="mt-2 truncate text-[13px] text-[#525252]"><span className="font-mono tabular-nums">→ {masked(i.recipient.display)}</span> · {i.recipient.holder} · {bankName(i.recipient.bank)}</p>
        </div>
        <p className="flex shrink-0 items-center gap-1.5 pt-1 text-[13px] text-[#525252]"><span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />{st.label}</p>
      </div>

      <div data-tour="bank-note" className="mt-5 border-l-2 border-teal-700 pl-4">
        <p className="flex items-center gap-2 text-[12px] text-[#737373]">
          <Icon name="spark" className="h-3.5 w-3.5 text-teal-700" />Сводка ИИ для аналитика<span className="font-mono">· {i.note.source === 'rules' ? 'по правилам' : 'Mistral'}</span>
        </p>
        <p className="mt-1.5 max-w-[68ch] text-[15px] leading-[22px]">{i.note.text}</p>
      </div>

      <dl className="mt-5 grid grid-cols-[112px_minmax(0,1fr)] gap-x-4 gap-y-2 border-t border-black/[0.06] pt-4 text-[13px]">
        {facts.map(([k, v, warn]) => (
          <div key={k} className="contents">
            <dt className="text-[#737373]">{k}</dt>
            <dd className={warn ? 'text-red-600' : 'text-[#171717]'}>{v}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-5 grid gap-5 border-t border-black/[0.06] pt-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-[12px] text-[#737373]">Причины</p>
          <ul className="space-y-1.5 text-[13px] text-[#525252]">{i.reasons.map(r => <li key={r}>{r}</li>)}</ul>
        </div>
        <div>
          <p className="mb-2 text-[12px] text-[#737373]">Сессия клиента</p>
          <ol className="space-y-1.5 text-[13px]">
            {i.timeline.length === 0 && <li className="text-[#737373]">событий нет</li>}
            {i.timeline.map((e, k) => (
              <li key={k} className="grid grid-cols-[44px_minmax(0,1fr)] gap-2">
                <span className="font-mono tabular-nums text-[#737373]">{time(e.ts)}</span><span className="text-[#525252]">{e.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {active && (
        <div className="mt-6 grid grid-cols-2 gap-2">
          <button disabled={busy} onClick={() => onDecide(i.id, 'block')}
            className="h-11 rounded-[10px] bg-red-600 text-[14px] font-medium text-white transition-[transform,background-color] duration-150 hover:bg-red-700 active:scale-[0.98] disabled:opacity-50">Заблокировать</button>
          <button disabled={busy} onClick={() => onDecide(i.id, 'release')}
            className="h-11 rounded-[10px] border border-black/[0.08] bg-[#f4f4f5] text-[14px] font-medium transition-[transform,background-color] duration-150 hover:bg-[#ececee] active:scale-[0.98] disabled:opacity-50">Разрешить</button>
        </div>
      )}
    </div>
  )
}

export default function BankPage() {
  return <div className="h-[100dvh]"><BankConsole /></div>
}
