import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money, startSandbox } from '../api'
import BankApp from '../phone/BankApp'
import { Device, DEVICE_H } from '../phone/Device'
import Starfield from '../Starfield'
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
const SPRING = { type: 'spring', stiffness: 420, damping: 40, mass: 0.7 } as const
type Box = { x: number; y: number; w: number; h: number }

const box = (el: Element): Box => { const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height } }
const same = (a: Box | null, b: Box | null, eps = 1) =>
  !!a && !!b && Math.abs(a.x - b.x) < eps && Math.abs(a.y - b.y) < eps && Math.abs(a.w - b.w) < eps && Math.abs(a.h - b.h) < eps

// Wait until the element stops moving (page transitions, smooth scroll, entrance animations) before the
// highlight jumps to it: no more «floating back and forth».
function settled(el: Element, maxMs = 1600): Promise<Box> {
  return new Promise(resolve => {
    let last = box(el), still = 0
    const t0 = performance.now()
    const tick = () => {
      const b = box(el)
      still = same(b, last, 0.5) ? still + 1 : 0
      last = b
      if (still >= 6 || performance.now() - t0 > maxMs) resolve(b)
      else requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

export default function Try() {
  const [ready, setReady] = useState(false)
  const [profile, setProfile] = useState<Profile>('aigerim')
  const [i, setI] = useState<number | null>(null)
  const [rect, setRect] = useState<Box | null>(null)
  const [busy, setBusy] = useState(false)
  const [epoch, setEpoch] = useState(0)
  const roots = useRef<Record<Profile, HTMLDivElement | null>>({ aigerim: null, erzhan: null, madina: null })
  const { stage } = useStage(1500)
  const vp = useViewport()
  const desktop = vp.w >= 900
  const scale = Math.min(1, (vp.h - 96) / DEVICE_H)

  const begin = useCallback(async (fresh: boolean) => {
    setReady(false)
    startSandbox(fresh)
    try {
      await api.director('reset')
      await api.setLang('aigerim', 'ru')  // the juror reads Russian first; ҚАЗ is one tap away
    } catch { /* the app shows its own offline banner */ }
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

  // run the step's world events, show the right phone, wait for the anchor to appear and settle,
  // then follow it frame by frame (rAF) — state changes only when it really moves
  useLayoutEffect(() => {
    if (!step) return
    let alive = true, raf = 0
    setRect(null)
    setProfile(step.profile)
    void (async () => {
      if (step.before) { setBusy(true); await pause(300); await step.before().catch(() => undefined); setBusy(false) }
      if (!step.target) return
      let el: Element | null = null
      for (let tries = 0; alive && !el && tries < 80; tries++) {
        el = roots.current[step.profile]?.querySelector(`[data-tour="${step.target}"]`) ?? null
        if (!el) await pause(120)
      }
      if (!alive || !el) return
      el.scrollIntoView({ block: 'center', behavior: 'smooth' })
      let cur = await settled(el)
      if (!alive) return
      setRect(cur)
      const follow = () => {
        const now = roots.current[step.profile]?.querySelector(`[data-tour="${step.target}"]`)
        if (now) { const b = box(now); if (!same(b, cur, 1.5)) { cur = b; setRect(b) } }
        raf = requestAnimationFrame(follow)
      }
      raf = requestAnimationFrame(follow)
    })()
    return () => { alive = false; cancelAnimationFrame(raf) }
  }, [step])

  // tapping the highlighted element yourself advances the tour
  const anchored = rect !== null
  useEffect(() => {
    if (!step?.target || step.next !== 'click' || !anchored) return
    const el = roots.current[step.profile]?.querySelector(`[data-tour="${step.target}"]`)
    const onTap = () => setTimeout(() => setI(n => (n == null ? n : n + 1)), 120)
    el?.addEventListener('click', onTap)
    return () => el?.removeEventListener('click', onTap)
  }, [step, anchored])

  const finish = () => { try { sessionStorage.setItem(TOUR_SEEN, '1') } catch { /* ignore */ } setI(null) }
  const next = async () => {
    if (i == null || !step) return
    if (i === STEPS.length - 1) return finish()
    const r = roots.current[step.profile]
    if (r && step.next === 'click') { r.querySelector<HTMLElement>(`[data-tour="${step.target}"]`)?.click(); return }  // the tap listener advances
    if (r && typeof step.next === 'function') { setBusy(true); await step.next(r); setBusy(false) }
    setI(i + 1)
  }

  // the card: measured once per content change, moved only with transforms
  const cardRef = useRef<HTMLDivElement>(null)
  const [cardH, setCardH] = useState(200)
  useLayoutEffect(() => {
    const el = cardRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setCardH(el.offsetHeight))
    ro.observe(el)
    return () => ro.disconnect()
  }, [step])
  const cardW = desktop ? 340 : vp.w - 24
  const pos = cardPos(rect, desktop, vp, cardW, cardH)
  const pad = 8

  return (
    <div className="relative flex h-[100dvh] flex-col overflow-hidden text-white">
      <Starfield />
      <header className="relative z-10 flex shrink-0 items-center gap-2 px-3 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))] md:px-6 md:pt-4">
        <Link to="/" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-500 shadow-[0_0_24px_rgba(52,211,153,.35)]"><Icon name="shield" className="h-5 w-5" /></Link>
        {desktop && <div className="mr-2 leading-tight"><div className="font-black">Qaqpan</div><div className="text-[11px] text-slate-400">попробуйте сами</div></div>}
        <div className="flex min-w-0 flex-1 gap-1 rounded-2xl bg-white/[0.06] p-1 ring-1 ring-white/10 backdrop-blur md:max-w-md">
          {PROFILES.map(p => (
            <button key={p.id} onClick={() => setProfile(p.id)}
              className={`relative min-w-0 flex-1 rounded-xl px-2 py-1.5 text-center text-xs font-semibold transition-colors duration-200 ${profile === p.id ? 'text-slate-900' : 'text-slate-300'}`}>
              {profile === p.id && <motion.span layoutId="tab" transition={SPRING} className="absolute inset-0 rounded-xl bg-white" />}
              <span className="relative block truncate">{p.name}</span>
              <span className="relative block truncate text-[10px] font-normal text-slate-500">{p.role}</span>
            </button>
          ))}
        </div>
        <div className="ml-auto shrink-0 text-right leading-tight">
          <div className="text-sm font-black tabular-nums text-emerald-400 md:text-xl">{money(stage?.saved ?? 0)}</div>
          <div className="text-[10px] text-slate-400">спасено</div>
        </div>
        <button onClick={() => void begin(true)} aria-label="Пройти заново" title="Пройти экскурсию заново"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/10 text-sm font-bold ring-1 ring-white/10">?</button>
      </header>

      <main className="relative z-10 flex min-h-0 flex-1 items-center justify-center md:pb-4">
        {desktop ? (
          <Device scale={scale}>
            {PROFILES.map(p => (
              <div key={`${p.id}-${epoch}`} ref={el => { roots.current[p.id] = el }} className={profile === p.id ? 'h-full' : 'hidden'}>
                {ready && <BankApp clientId={p.id} />}
              </div>
            ))}
          </Device>
        ) : PROFILES.map(p => (
          <div key={`${p.id}-${epoch}`} ref={el => { roots.current[p.id] = el }} className={profile === p.id ? 'h-full w-full bg-slate-50' : 'hidden'}>
            {ready && <BankApp clientId={p.id} />}
          </div>
        ))}
      </main>

      <AnimatePresence>
        {step && (
          <motion.div key="tour" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}
            className="pointer-events-none fixed inset-0 z-[60]">
            {/* spotlight: one element, moved with transforms; the dim is its huge shadow */}
            <motion.div className="fixed left-0 top-0 rounded-2xl" style={{ willChange: 'transform' }}
              initial={false}
              animate={rect
                ? { x: rect.x - pad, y: rect.y - pad, width: rect.w + pad * 2, height: rect.h + pad * 2, boxShadow: '0 0 0 9999px rgba(2,6,23,.55), 0 0 0 3px rgba(52,211,153,1)' }
                : { x: vp.w / 2, y: vp.h / 2, width: 0, height: 0, boxShadow: '0 0 0 9999px rgba(2,6,23,.55), 0 0 0 0px rgba(52,211,153,0)' }}
              transition={SPRING} />
            <motion.div ref={cardRef} className="pointer-events-auto fixed left-0 top-0 rounded-3xl bg-white/95 p-4 text-slate-900 shadow-[0_24px_70px_rgba(0,0,0,.45)] ring-1 ring-black/5 backdrop-blur-xl"
              style={{ width: cardW, willChange: 'transform' }}
              initial={{ x: pos.x, y: pos.y + 16, opacity: 0 }} animate={{ x: pos.x, y: pos.y, opacity: 1 }} transition={SPRING}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-600">{i! + 1} / {STEPS.length}</span>
                <button onClick={finish} className="text-xs text-slate-400">Пропустить</button>
              </div>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }}>
                  <div className="mt-1 text-[17px] font-bold leading-snug">{step.title}</div>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-slate-600">{step.text}</p>
                </motion.div>
              </AnimatePresence>
              <div className="mt-3 flex gap-2">
                {i! > 0 && i! < STEPS.length - 1 && (
                  <button onClick={() => setI(i! - 1)} className="rounded-2xl px-4 py-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 active:scale-[0.97]">Назад</button>
                )}
                {i === STEPS.length - 1 && (
                  <button onClick={() => void begin(true)} className="rounded-2xl px-4 py-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 active:scale-[0.97]">Пройти заново</button>
                )}
                <button onClick={() => void next()} disabled={busy}
                  className="flex-1 rounded-2xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-transform active:scale-[0.97] disabled:opacity-60">
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

function cardPos(rect: Box | null, desktop: boolean, vp: { w: number; h: number }, w: number, h: number) {
  const margin = 12
  if (desktop) {
    if (!rect) return { x: vp.w / 2 - w / 2, y: vp.h / 2 - h / 2 }
    const right = rect.x + rect.w + 28
    const x = right + w + margin < vp.w ? right : Math.max(margin, rect.x - w - 28)
    return { x, y: Math.max(margin, Math.min(vp.h - h - margin, rect.y + rect.h / 2 - h / 2)) }
  }
  // phone: the card sits at the screen edge away from the highlighted element
  const top = { x: margin, y: margin + 4 }
  const bottom = { x: margin, y: vp.h - h - margin }
  if (!rect) return bottom
  return rect.y + rect.h / 2 > vp.h / 2 ? top : bottom
}

function useViewport() {
  const read = () => ({ w: window.innerWidth, h: window.innerHeight })
  const [vp, setVp] = useState(read)
  useEffect(() => {
    let raf = 0
    const h = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => setVp(read())) }
    window.addEventListener('resize', h)
    return () => { window.removeEventListener('resize', h); cancelAnimationFrame(raf) }
  }, [])
  return vp
}
