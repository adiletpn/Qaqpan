import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api, money, type FamilyRequest, type Lang, type Notice, type Shield } from '../api'
import { tr } from '../i18n'
import { buzz, EASE, SPRING } from '../motion'
import { Button, Card, Header, Icon } from '../ui'
import { SpeakButton } from './Speak'

type K = Parameters<typeof tr>[1]

const hhmm = (ts: number) => new Date(ts * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

// ------------------------------------------------------------------ push notification (lock-screen style)

export function PushBanner({ notice, lang, onOpen, onClose }: { notice: Notice; lang: Lang; onOpen: () => void; onClose: () => void }) {
  const urgent = notice.kind === 'family_request'
  useEffect(() => { buzz(urgent ? [120, 80, 120] : 40) }, [urgent])
  return (
    <motion.div initial={{ y: -140, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -140, opacity: 0 }} transition={SPRING}
      drag="y" dragConstraints={{ top: 0, bottom: 0 }} onDragEnd={(_, i) => { if (i.offset.y < -30) onClose() }}
      className="absolute inset-x-2 top-2 z-40">
      <div className={`rounded-2xl p-3 shadow-2xl ring-1 backdrop-blur ${urgent ? 'bg-slate-900/95 text-white ring-red-500/60' : 'bg-white/95 ring-slate-200'}`}>
        <div className="flex items-start gap-3">
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${urgent ? 'bg-red-500' : 'bg-teal-700'} text-white`}>
            <Icon name="shield" className="h-5 w-5" />
          </span>
          <button data-tour="push" onClick={onOpen} className="min-w-0 flex-1 text-left">
            <div className="flex items-center justify-between text-[11px] font-semibold opacity-70">
              <span>{notice.title}</span><span>{tr(lang, 'now')}</span>
            </div>
            <div className="mt-0.5 text-sm font-semibold leading-snug">{notice.body}</div>
          </button>
          <button onClick={onClose} className="opacity-50" aria-label={tr(lang, 'close')}><Icon name="x" className="h-4 w-4" /></button>
        </div>
      </div>
    </motion.div>
  )
}

// ------------------------------------------------------------------ the guardian's decision screen

export function FamilySheet({ req, clientId, lang, onDone, onClose }: { req: FamilyRequest; clientId: string; lang: Lang; onDone: () => void; onClose: () => void }) {
  const L = (k: K) => tr(lang, k)
  const [busy, setBusy] = useState(false)
  const [confirmAllow, setConfirmAllow] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const decide = async (approve: boolean) => {
    setBusy(true); setErr(null)
    try { await api.family(req.id, clientId, approve); onDone() } catch (e) { setErr(e instanceof Error ? e.message : L('error')) } finally { setBusy(false) }
  }
  const minutes = Math.max(1, Math.ceil(req.expires_in / 60))
  return (
    <motion.div data-tour="family-sheet" initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }} transition={{ duration: 0.38, ease: EASE }}
      className="absolute inset-0 z-30 flex flex-col bg-slate-50 shadow-2xl">
      <div className="flex items-center justify-between bg-red-600 px-4 pb-3 pt-3 text-white">
        <div className="flex items-center gap-2 text-xs font-semibold"><Icon name="family" className="h-4 w-4" />{L('family_shield')}</div>
        <button onClick={onClose} className="opacity-80" aria-label={L('close')}><Icon name="x" className="h-5 w-5" /></button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 pb-4 pt-4">
        <h3 data-tour="family-headline" className="text-[22px] font-semibold leading-tight text-slate-900">{req.headline}</h3>
        <SpeakButton lang={lang} text={`${req.headline}. ${req.explanation} ${req.advice}`} />
        <p className="text-[15px] leading-relaxed text-slate-700">{req.explanation}</p>

        <Card className="!p-3">
          <div className="text-xs font-semibold text-slate-500">{money(req.amount)} → {req.holder}</div>
          <div className="mt-0.5 font-mono text-xs text-slate-400">{req.account}</div>
        </Card>

        {req.timeline.length > 0 && (
          <Card className="!p-3">
            <div className="mb-2 text-xs font-semibold text-slate-500">{L('what_happened')}</div>
            <ol className="relative space-y-2 border-l-2 border-slate-200 pl-3">
              {req.timeline.map((e, i) => (
                <li key={i} className="text-sm">
                  <span className="absolute -left-[5px] mt-1.5 h-2 w-2 rounded-full bg-red-500" />
                  <span className="mr-2 font-mono text-xs text-slate-400">{hhmm(e.ts)}</span>{e.text}
                </li>
              ))}
            </ol>
          </Card>
        )}

        <div className="rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-200">
          <div className="text-xs font-semibold text-amber-700">{L('what_to_do')}</div>
          <p className="mt-1 text-sm leading-relaxed text-amber-950">{req.advice}</p>
        </div>

        {err && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</div>}
        {!confirmAllow
          ? <Button tone="ghost" disabled={busy} onClick={() => setConfirmAllow(true)}>{L('allow_after_talk')}</Button>
          : (
            <div className="animate-[pop_.2s_ease-out] rounded-2xl bg-white p-3 text-center ring-1 ring-slate-200">
              <div className="text-sm text-slate-600">{L('confirm_bio')}</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button tone="light" onClick={() => setConfirmAllow(false)}>{L('back')}</Button>
                <Button disabled={busy} onClick={() => decide(true)}>{L('confirm')}</Button>
              </div>
            </div>
          )}
        <div className="text-center text-xs text-slate-400">{minutes} {L('min_left')}</div>
      </div>
      <div className="space-y-2 border-t border-slate-200 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 shadow-[0_-8px_24px_rgba(0,0,0,0.06)]">
        <a href={`tel:${req.ward_phone.replace(/\s/g, '')}`}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-4 py-3 text-[15px] font-semibold text-white active:bg-emerald-700">
          <Icon name="phone" />{L('call_back')} · {req.ward_title}
        </a>
        <Button tour="decline" tone="danger" disabled={busy} onClick={() => decide(false)}>{L('decline_tr')}</Button>
      </div>
    </motion.div>
  )
}

// ------------------------------------------------------------------ shield settings / explainer

// Consent: what the guardian sees and never sees (shown before and after connecting the shield)
const CONSENT: Record<Lang, { sees: string[]; never: string[] }> = {
  ru: {
    sees: ['сумму и получателя только остановленного перевода', 'что идёт звонок — без номера и разговора',
      'вердикт проверенных вами сообщений'],
    never: ['ваш баланс и другие операции', 'содержание звонков и переписки', 'ваш пароль и коды'],
  },
  kk: {
    sees: ['тек тоқтатылған аударымның сомасы мен алушысы', 'қоңырау жүріп жатқаны — нөмірсіз және әңгімесіз',
      'сіз тексерген хабарламалардың қорытындысы'],
    never: ['балансыңыз бен басқа операциялар', 'қоңыраулар мен хат алмасудың мазмұны', 'құпиясөз бен кодтар'],
  },
}

// Kazakh puts the amount first: «200 000 ₸ бастап күдікті аударымдар растауды күтеді»
const limitLine = (lang: Lang, limit: number) => lang === 'kk'
  ? `${money(limit)} бастап күдікті аударымдар растауды күтеді.`
  : `Подозрительные переводы от ${money(limit)} ждут подтверждения.`

const EXPLAIN: Record<'ward' | 'guardian' | 'none', Record<Lang, string[]>> = {
  ward: {
    ru: ['Обычные переводы и покупки проходят как раньше.',
      'Если крупный перевод похож на обман, он ждёт ответа вашего близкого. Без его ответа деньги не уйдут.',
      'Если близкий не ответит за 15 минут, перевод проверит сотрудник банка. Сам он не уйдёт.',
      'Отключить щит можно, но только через 24 часа — так мошенник не сможет уговорить вас сделать это по телефону.'],
    kk: ['Кәдімгі аударымдар мен сатып алулар бұрынғыдай өтеді.',
      'Егер үлкен аударым алаяқтыққа ұқсаса, ол жақын адамыңыздың жауабын күтеді. Оның жауабынсыз ақша кетпейді.',
      'Жақын адамыңыз 15 минут ішінде жауап бермесе, аударымды банк қызметкері тексереді. Ол өздігінен кетпейді.',
      'Қалқанды өшіруге болады, бірақ тек 24 сағаттан кейін — алаяқ сізді телефон арқылы бұған көндіре алмайды.'],
  },
  guardian: {
    ru: ['Вы получите уведомление только при крупном подозрительном переводе — обычные покупки вас не касаются.',
      'В уведомлении — что происходит простыми словами и что Qaqpan видел сегодня.',
      'Сначала позвоните близкому на его обычный номер. Потом решите: отклонить или разрешить.',
      'Если не ответите за 15 минут, перевод не уйдёт сам — его проверит сотрудник банка.'],
    kk: ['Хабарлама тек үлкен күдікті аударым кезінде келеді — кәдімгі сатып алулар сізге қатысты емес.',
      'Хабарламада не болып жатқаны қарапайым тілмен және Qaqpan бүгін не байқағаны жазылады.',
      'Алдымен жақын адамыңызға әдеттегі нөміріне қоңырау шалыңыз. Содан кейін шешім қабылдаңыз: рұқсат бермеу немесе рұқсат беру.',
      '15 минут ішінде жауап бермесеңіз, аударым өздігінен кетпейді — оны банк қызметкері тексереді.'],
  },
  none: {
    ru: ['Выберите близкого человека — сына, дочь, брата.',
      'Он получит приглашение и должен его принять: без согласия связь не создаётся.',
      'Подозрительные крупные переводы будут ждать его подтверждения.'],
    kk: ['Жақын адамды таңдаңыз — ұлыңызды, қызыңызды, ағаңызды.',
      'Ол шақыру алып, оны қабылдауы керек: келісімсіз байланыс жасалмайды.',
      'Күдікті үлкен аударымдар оның растауын күтеді.'],
  },
}

export function FamilyScreen({ clientId, lang, shield, onBack, onChanged }: { clientId: string; lang: Lang; shield: Shield; onBack: () => void; onChanged: () => void }) {
  const L = (k: K) => tr(lang, k)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const act = async (f: () => Promise<unknown>) => {
    setBusy(true); setErr(null)
    try { await f(); onChanged() } catch (e) { setErr(e instanceof Error ? e.message : L('error')) } finally { setBusy(false) }
  }
  const when = (ts: number) => new Date(ts * 1000).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  return (
    <div className="pb-8">
      <Header title={L('family_shield')} onBack={onBack} />
      <div className="space-y-3 px-4">
        {shield.role === 'ward' && (
          <Card>
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-teal-700 text-white"><Icon name="family" /></span>
              <div>
                <div className="text-xs text-slate-500">{L('guardian')}</div>
                <div className="font-semibold">{shield.guardian_name} · {shield.guardian_title}</div>
              </div>
              <span className={`ml-auto rounded-full px-2 py-0.5 text-xs font-semibold ${shield.disable_at ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>
                {shield.disable_at ? `${L('shield_off_at')} ${when(shield.disable_at)}` : L('shield_on')}
              </span>
            </div>
            <div className="mt-3 text-sm text-slate-600">{limitLine(lang, shield.limit)}</div>
          </Card>
        )}
        {shield.role === 'guardian' && shield.wards.map(w => (
          <Card key={w.ward_id}>
            <div className="text-xs text-slate-500">{L('you_protect')}</div>
            <div className="text-lg font-semibold">{w.title} · {w.name}</div>
            <div className="mt-1 text-sm text-slate-600">{limitLine(lang, w.limit)}</div>
            {w.disable_at && (
              <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
                {L('shield_off_at')} {when(w.disable_at)}
                <Button className="mt-2" disabled={busy} onClick={() => act(() => api.shieldKeep(w.ward_id))}>{L('shield_keep')}</Button>
              </div>
            )}
          </Card>
        ))}
        {shield.role === 'none' && (
          <Card>
            <div className="text-lg font-semibold">{L('connect_close')}</div>
          </Card>
        )}

        {shield.role !== 'guardian' && (
          <Card>
            <div className="mb-2 text-sm font-semibold text-slate-500">{lang === 'kk' ? 'Жақын адамыңыз не көреді' : 'Что увидит ваш близкий'}</div>
            <ul className="space-y-1.5 text-sm text-slate-700">
              {CONSENT[lang].sees.map(x => <li key={x} className="flex gap-2"><span className="text-emerald-600">✓</span>{x}</li>)}
            </ul>
            <div className="mb-2 mt-3 text-sm font-semibold text-slate-500">{lang === 'kk' ? 'Ешқашан көрмейді' : 'Никогда не увидит'}</div>
            <ul className="space-y-1.5 text-sm text-slate-700">
              {CONSENT[lang].never.map(x => <li key={x} className="flex gap-2"><span className="text-slate-400">✕</span>{x}</li>)}
            </ul>
          </Card>
        )}

        <Card>
          <div className="flex items-center gap-2 font-semibold"><Icon name="key" className="h-5 w-5 text-teal-700" />{L('codeword')}</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{L('codeword_text')}</p>
          {shield.codeword ? (
            <div className="mt-3 flex items-center justify-between">
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">✓ {L('codeword_done')}</span>
              <button disabled={busy} onClick={() => act(() => api.codeword(clientId, false))} className="text-xs font-semibold text-slate-400">{L('codeword_undo')}</button>
            </div>
          ) : (
            <Button className="mt-3" tone="light" disabled={busy} onClick={() => act(() => api.codeword(clientId, true))}>{L('codeword_agree')}</Button>
          )}
        </Card>

        <Card>
          <div className="mb-2 text-sm font-semibold text-slate-500">{L('how_it_works')}</div>
          <ol className="space-y-2 text-sm text-slate-700">
            {EXPLAIN[shield.role][lang].map((s, i) => (
              <li key={i} className="flex gap-2"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-teal-700 text-[11px] font-bold text-white">{i + 1}</span>{s}</li>
            ))}
          </ol>
        </Card>

        {err && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</div>}
        {shield.role === 'ward' && (shield.disable_at
          ? <Button disabled={busy} onClick={() => act(() => api.shieldKeep(clientId))}>{L('shield_keep')}</Button>
          : <Button tone="ghost" disabled={busy} onClick={() => act(() => api.shieldDisable(clientId))}>{L('shield_disable')}</Button>)}
      </div>
    </div>
  )
}
