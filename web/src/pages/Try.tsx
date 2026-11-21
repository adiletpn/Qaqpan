import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money, startSandbox } from '../api'
import { EASE } from '../motion'
import BankApp from '../phone/BankApp'
import { Icon } from '../ui'
import { useStage } from './shared'

// Self-guided demo for anyone with the link (a juror on a phone or a laptop): an own sandbox on the server,
// three phones kept alive (switching profiles keeps each screen), and a guided tour that highlights the next
// button. Tap the highlighted button yourself or press «Далее» — the tour does it for you.

type Profile = 'aigerim' | 'erzhan' | 'madina'
const PROFILES: { id: Profile; name: string; role: string }[] = [
  { id: 'aigerim', name: 'Айгерим, 52', role: 'клиентка' },
  { id: 'erzhan', name: 'Ержан, 27', role: 'её сын' },
  { id: 'madina', name: 'Мадина, 34', role: 'другая клиентка' },
]

type Step = {
  profile: Profile
  title: string
  text: string
  target?: string                    // data-tour anchor inside the visible phone
  before?: () => Promise<unknown>    // scripted world events (SMS, a call, the scammer's transfer…)
  next?: 'click' | ((root: HTMLElement) => Promise<unknown> | void)
  cta?: string
}

const pause = (ms: number) => new Promise(r => setTimeout(r, ms))
const buttons = (root: HTMLElement, sel: string) => [...root.querySelectorAll<HTMLButtonElement>(sel)]

async function answer(root: HTMLElement, plan: boolean[]) {
  const q = root.querySelector('[data-tour="questions"]')
  if (!q) return
  const cards = [...q.children].filter(c => c.querySelector('button'))
  for (let i = 0; i < plan.length && i < cards.length; i++) {
    const [yes, no] = [...cards[i].querySelectorAll('button')]
    ;(plan[i] ? yes : no)?.click()
    await pause(220)
  }
  await pause(150)
  root.querySelector<HTMLButtonElement>('[data-tour="answer"]')?.click()
}

const STEPS: Step[] = [
  { profile: 'aigerim', title: 'Вы — Айгерим, 52 года',
    text: 'За 2 минуты пройдёте весь путь мошенника: написали → позвонили → уговорили перевести → получили деньги. Qaqpan стоит на каждом шаге. Нажимайте подсвеченные кнопки или «Далее».',
    cta: 'Начать' },
  { profile: 'aigerim', target: 'sms', before: () => api.director('sms'), next: 'click', title: 'Шаг 1 · Написали',
    text: 'Пришло SMS: «Срок вашей ЭЦП истекает сегодня, продлите по ссылке». Откройте его — Qaqpan проверит.' },
  { profile: 'aigerim', target: 'check-btn', next: 'click', title: 'Проверка за секунду',
    text: 'Нажмите «Проверить». Так же проверяются ссылки и скриншоты из WhatsApp и Telegram.' },
  { profile: 'aigerim', target: 'verdict', title: 'Мошенничество',
    text: 'Ссылка подделана под eGov, а ЭЦП по SMS не продлевают. Причины — простыми словами, на русском или казахском.',
    next: root => buttons(root, 'button[aria-label="back"]')[0]?.click() },
  { profile: 'aigerim', target: 'call-accept', before: () => api.director('call'), next: 'click', title: 'Шаг 2 · Позвонили',
    text: 'Звонит «служба безопасности банка». Номер на экране мошенник может подделать. Ответьте на звонок.' },
  { profile: 'aigerim', target: 'verify', next: 'click', title: '«Банк мне звонит?»',
    text: 'Одна кнопка во время звонка: Qaqpan сверяется с журналом звонков самого банка — его подделать нельзя.' },
  { profile: 'aigerim', target: 'verify-sheet', title: 'Банк вам НЕ звонит',
    text: 'Сотрудники банка ей сейчас не звонят, на этот номер уже жаловались. Значит, на линии мошенник.',
    next: root => root.querySelector<HTMLButtonElement>('[data-tour="verify-done"]')?.click() },
  { profile: 'aigerim', target: 'send', before: () => api.director('transfer_aigerim'), next: 'click', title: 'Шаг 3 · Уговорили перевести',
    text: 'Мошенник диктует: «переведите 900 000 ₸ на безопасный счёт». Реквизиты уже заполнены — нажмите «Перевести».' },
  { profile: 'aigerim', target: 'questions', title: 'Пауза и три вопроса',
    text: 'Идёт звонок, получатель новый, это больше половины денег — Qaqpan ставит паузу. Мошенник подсказал отвечать «Нет». Нажмите «Далее» — ответим за неё.',
    next: root => answer(root, [false, false, false]) },
  { profile: 'aigerim', target: 'result', title: 'Подсказанные ответы не помогли',
    text: 'Перевод новому получателю больше 200 000 ₸ ждёт решения сына. Разбить сумму на части или «положить трубку и перевести самой» тоже не поможет.' },
  { profile: 'erzhan', target: 'family-pending', next: 'click', title: 'Теперь вы — Ержан, сын',
    text: 'Он на работе. Пришло уведомление: «Маму, возможно, обманывают мошенники». Откройте его.' },
  { profile: 'erzhan', target: 'family-headline', title: 'Всё простыми словами',
    text: 'Что происходит, что Qaqpan видел сегодня, что сделать и кнопка «Позвонить маме». Без ответа сына деньги не уйдут, а через 15 минут перевод проверит банк.' },
  { profile: 'erzhan', target: 'decline', next: 'click', title: 'Отклоните перевод',
    text: 'Решение принимает только сын — ни мама, ни мошенник с её телефоном нажать за него не могут.' },
  { profile: 'aigerim', target: 'complain', next: 'click', title: 'Деньги мамы в безопасности',
    text: 'Айгерим сообщает о мошенниках. Перевод остановлен во время звонка, поэтому жалоба подтверждённая: счёт помечается для всех клиентов банка.' },
  { profile: 'madina', target: 'send', before: async () => { await api.director('end_call'); await api.director('transfer_madina') }, next: 'click',
    title: 'Шаг 4 · Получили деньги',
    text: 'Вы — Мадина. Покупает iPhone на OLX и платит 150 000 ₸ на тот же счёт: другая легенда, тот же мошенник. Нажмите «Перевести».' },
  { profile: 'madina', target: 'result', title: '«На этот счёт поступали жалобы»',
    text: 'Мадину остановили до потери денег: одна остановленная попытка защитила другого клиента. Банковская тайна соблюдена — о получателе ни слова, кроме жалоб.',
    next: root => answer(root, [true, true, false]) },
  { profile: 'madina', title: 'Это весь путь: 1 050 000 ₸ спасено',
    text: 'Попробуйте сами: «Спросить Qaqpan» — ИИ-помощник, который видит ситуацию клиента; «Семейный щит» у Айгерим нельзя отключить быстрее чем за 24 часа; «Проверить сообщение» — вставьте своё SMS или скриншот.',
    cta: 'Свободный режим' },
]

const TOUR_SEEN = 'qaqpan.try.seen'

export default function Try() {
  const [ready, setReady] = useState(false)
  const [profile, setProfile] = useState<Profile>('aigerim')
  const [i, setI] = useState<number | null>(null)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [busy, setBusy] = useState(false)
  const [epoch, setEpoch] = useState(0)
  const roots = useRef<Record<Profile, HTMLDivElement | null>>({ aigerim: null, erzhan: null, madina: null })
  const { stage } = useStage(1500)
  const vw = useWidth()
  const desktop = vw >= 900

  const begin = useCallback(async (fresh: boolean) => {
    setReady(false)
    startSandbox(fresh)
    try {
      await api.director('reset')
      await api.setLang('aigerim', 'ru')  // the juror reads Russian first; ҚАЗ is one tap away
    } catch { /* offline banner in the app says the rest */ }
    setEpoch(e => e + 1)
    setProfile('aigerim')
    setReady(true)
    setI(0)
  }, [])

  useEffect(() => {
    let seen = false
    try { seen = !!sessionStorage.getItem(TOUR_SEEN) } catch { /* ignore */ }
    startSandbox()
    if (seen) { setReady(true); return }
    void begin(true)
  }, [begin])

  const step = i != null ? STEPS[i] : null
  const root = step ? roots.current[step.profile] : null

  // run the step's world events, switch the phone, then find the anchor (it may appear after an animation)
  useLayoutEffect(() => {
    if (!step) return
    let alive = true
    setRect(null)
    setProfile(step.profile)
    void (async () => {
      if (step.before) { setBusy(true); await pause(350); await step.before().catch(() => undefined); setBusy(false) }
      for (let tries = 0; alive && tries < 60; tries++) {
        const el = step.target ? roots.current[step.profile]?.querySelector(`[data-tour="${step.target}"]`) : null
        if (!step.target) return
        if (el) {
          el.scrollIntoView({ block: 'center', behavior: 'smooth' })
          await pause(420)
          if (alive) setRect(el.getBoundingClientRect())
          return
        }
        await pause(150)
      }
    })()
    return () => { alive = false }
  }, [step])

  // keep the highlight on the element while things move; tapping it yourself advances the tour
  const hasRect = rect !== null
  useEffect(() => {
    if (!step?.target || !root) return
    const el = root.querySelector(`[data-tour="${step.target}"]`)
    const measure = () => { const e = root.querySelector(`[data-tour="${step.target}"]`); if (e) setRect(e.getBoundingClientRect()) }
    const t = setInterval(measure, 400)
    window.addEventListener('resize', measure)
    const onTap = () => { if (step.next === 'click') setTimeout(() => setI(n => (n == null ? n : n + 1)), 120) }
    el?.addEventListener('click', onTap)
    return () => { clearInterval(t); window.removeEventListener('resize', measure); el?.removeEventListener('click', onTap) }
  }, [step, root, hasRect])

  const finish = () => { try { sessionStorage.setItem(TOUR_SEEN, '1') } catch { /* ignore */ } setI(null) }
  const next = async () => {
    if (i == null || !step) return
    if (i === STEPS.length - 1) return finish()
    const r = roots.current[step.profile]
    if (r && step.next === 'click') r.querySelector<HTMLElement>(`[data-tour="${step.target}"]`)?.click()
    else if (r && typeof step.next === 'function') { setBusy(true); await step.next(r); setBusy(false) }
    else setI(i + 1)
    if (step.next === 'click') return  // the tap listener advances
    if (typeof step.next === 'function') setI(i + 1)
  }

  const pad = 8
  const card = cardPosition(rect, desktop)

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-slate-950 text-white">
      <header className="flex shrink-0 items-center gap-2 px-3 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))] md:px-6 md:pt-4">
        <Link to="/" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-500"><Icon name="shield" className="h-5 w-5" /></Link>
        {desktop && <div className="mr-2 leading-tight"><div className="font-black">Qaqpan</div><div className="text-[11px] text-slate-400">попробуйте сами</div></div>}
        <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto rounded-2xl bg-white/5 p-1 md:max-w-md">
          {PROFILES.map(p => (
            <button key={p.id} onClick={() => setProfile(p.id)}
              className={`min-w-0 flex-1 rounded-xl px-2 py-1.5 text-center text-xs font-semibold transition ${profile === p.id ? 'bg-white text-slate-900' : 'text-slate-300'}`}>
              <div className="truncate">{p.name}</div>
              <div className={`truncate text-[10px] font-normal ${profile === p.id ? 'text-slate-500' : 'text-slate-500'}`}>{p.role}</div>
            </button>
          ))}
        </div>
        <div className="ml-auto shrink-0 text-right leading-tight">
          <div className="text-sm font-black tabular-nums text-emerald-400 md:text-xl">{money(stage?.saved ?? 0)}</div>
          <div className="text-[10px] text-slate-400">спасено</div>
        </div>
        <button onClick={() => void begin(true)} aria-label="Пройти заново" title="Пройти экскурсию заново"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/10 text-sm font-bold">?</button>
      </header>

      <main className="relative flex min-h-0 flex-1 items-center justify-center md:pb-6">
        {PROFILES.map(p => (
          <div key={`${p.id}-${epoch}`} ref={el => { roots.current[p.id] = el }}
            className={profile === p.id ? (desktop ? 'h-full max-h-[820px] w-[390px] overflow-hidden rounded-[40px] border-[8px] border-slate-800 bg-slate-50 shadow-2xl' : 'h-full w-full bg-slate-50') : 'hidden'}>
            {ready && <BankApp clientId={p.id} />}
          </div>
        ))}
      </main>

      <AnimatePresence>
        {step && (
          <motion.div key="tour" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="pointer-events-none fixed inset-0 z-[60]">
            {rect ? (
              <div className="fixed rounded-2xl transition-all duration-300"
                style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2,
                  boxShadow: '0 0 0 9999px rgba(2,6,23,.55), 0 0 0 3px #34d399' }} />
            ) : (
              <div className="fixed inset-0 bg-slate-950/55" />
            )}
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}
              className="pointer-events-auto fixed rounded-3xl bg-white p-4 text-slate-900 shadow-[0_20px_60px_rgba(0,0,0,.35)]" style={card}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-600">{i! + 1} / {STEPS.length}</span>
                <button onClick={finish} className="text-xs text-slate-400">Пропустить</button>
              </div>
              <div className="mt-1 text-[17px] font-bold leading-snug">{step.title}</div>
              <p className="mt-1.5 text-[14px] leading-relaxed text-slate-600">{step.text}</p>
              <div className="mt-3 flex gap-2">
                {i! > 0 && i! < STEPS.length - 1 && (
                  <button onClick={() => setI(i! - 1)} className="rounded-2xl px-4 py-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200">Назад</button>
                )}
                {i === STEPS.length - 1 && (
                  <button onClick={() => void begin(true)} className="rounded-2xl px-4 py-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200">Пройти заново</button>
                )}
                <button onClick={() => void next()} disabled={busy}
                  className="flex-1 rounded-2xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                  {busy ? '…' : step.cta ?? 'Далее'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

type Pos = { left?: number | string; right?: number | string; top?: number | string; bottom?: number | string; width?: number }

function cardPosition(rect: DOMRect | null, desktop: boolean): Pos {
  const vw = window.innerWidth, vh = window.innerHeight
  if (desktop) {
    const W = 340
    if (!rect) return { width: W, left: vw / 2 - W / 2, top: vh / 2 - 120 }
    const phoneRight = vw / 2 + 195 + 24
    const left = phoneRight + W + 16 < vw ? phoneRight : Math.max(16, vw / 2 - 195 - W - 24)
    return { width: W, left, top: Math.max(16, Math.min(vh - 260, rect.top - 20)) }
  }
  // phone: the card sits at the edge away from the highlighted element
  const base: Pos = { left: 12, right: 12 }
  if (!rect) return { ...base, bottom: 'max(12px, env(safe-area-inset-bottom))' }
  return rect.top + rect.height / 2 > vh / 2 ? { ...base, top: 'max(12px, env(safe-area-inset-top))' } : { ...base, bottom: 'max(12px, env(safe-area-inset-bottom))' }
}

function useWidth() {
  const [w, setW] = useState(() => window.innerWidth)
  useEffect(() => {
    const h = () => setW(window.innerWidth)
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  }, [])
  return w
}
