import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Lang } from '../api'
import { tr } from '../i18n'
import { buzz, EASE, SPRING } from '../motion'
import { Header, Icon } from '../ui'
import { Thinking } from './Thinking'
import { useTypewriter } from './typewriter'
import { SpeakButton } from './Speak'
import { QUICK } from './quick'

type Msg = { role: 'user' | 'assistant'; content: string; offline?: boolean }


export function AssistantScreen({ clientId, lang, onBack, seed }: { clientId: string; lang: Lang; onBack: () => void; seed?: string | null }) {
  const L = (k: Parameters<typeof tr>[1]) => tr(lang, k)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [msgs, busy])
  // while the answer «types», keep the newest line in view without smooth-scroll fights
  const stick = useCallback(() => bottom.current?.scrollIntoView({ block: 'end' }), [])
  const [typed, setTyped] = useState(-1)  // index of the answer to reveal with the typewriter

  const send = async (content: string) => {
    const q = content.trim()
    if (!q || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: q }]
    setMsgs(next); setText(''); setBusy(true)
    try {
      const r = await api.assistant(clientId, lang, next.map(({ role, content }) => ({ role, content })))
      buzz(15)
      setMsgs(m => { setTyped(m.length); return [...m, { role: 'assistant', content: r.reply, offline: r.source === 'offline' }] })
    } catch (e) {
      setMsgs(m => [...m, { role: 'assistant', content: e instanceof Error ? e.message : L('error'), offline: true }])
    } finally { setBusy(false) }
  }

  // a question tapped on the home screen is sent right away, once
  const seeded = useRef(false)
  useEffect(() => {
    if (seed && !seeded.current) { seeded.current = true; send(seed) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed])

  return (
    <div className="flex min-h-full flex-col">
      <Header title={L('assistant')} onBack={onBack} />
      {/* Law «On artificial intelligence» (in force since 18.01.2026): users must know the service uses AI */}
      <div className="mx-4 mb-2 flex items-center gap-2 px-1 py-1 text-xs text-slate-500">
        <span className="rounded-md bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">{lang === 'kk' ? 'ЖИ' : 'ИИ'}</span>
        {lang === 'kk' ? 'Жасанды интеллект жауап береді, қателесуі мүмкін' : 'Отвечает искусственный интеллект, может ошибаться'}
      </div>
      <div className="flex-1 space-y-2.5 px-4 pb-4">
        <Bubble role="assistant" content={L('assistant_hello')} lang={lang} />
        <AnimatePresence initial={false}>
          {msgs.length === 0 && (
            <motion.div key="quick" exit={{ opacity: 0, height: 0 }} className="flex flex-wrap gap-2 pt-1">
              {QUICK[lang].map((q, i) => (
                <motion.button key={q} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.06, ease: EASE }}
                  whileTap={{ scale: 0.96 }} onClick={() => send(q)}
                  className="rounded-xl bg-white px-3 py-2 text-left text-[13px] text-slate-800 ring-1 ring-black/[0.08]">
                  {q}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        {msgs.map((m, i) => <Bubble key={i} role={m.role} content={m.content} note={m.offline ? L('ai_offline') : undefined}
          type={m.role === 'assistant' && i === msgs.length - 1 && i === typed} onGrow={stick} lang={lang} />)}
        <AnimatePresence initial={false}>
          {busy && (
            <motion.div key="thinking" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 40 }} exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }} className="overflow-hidden">
              <Thinking lang={lang} />
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottom} />
      </div>
      <form onSubmit={e => { e.preventDefault(); send(text) }}
        className="sticky bottom-0 flex items-end gap-2 border-t border-slate-200 bg-white/95 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur">
        <textarea value={text} onChange={e => setText(e.target.value)} rows={1} placeholder={L('ask_placeholder')}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text) } }}
          className="max-h-28 min-h-11 flex-1 resize-none rounded-2xl border-0 bg-slate-100 px-4 py-2.5 text-[15px] focus:outline-none focus:ring-2 focus:ring-teal-600" />
        <motion.button whileTap={{ scale: 0.9 }} type="submit" disabled={!text.trim() || busy} aria-label="send"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-teal-700 text-white disabled:opacity-40">
          <Icon name="arrowup" className="h-5 w-5" />
        </motion.button>
      </form>
    </div>
  )
}

function Bubble({ role, content, note, type = false, onGrow, lang }: { role: Msg['role']; content: string; note?: string; type?: boolean; onGrow?: () => void; lang: Lang }) {
  const mine = role === 'user'
  const text = useTypewriter(content, type, onGrow)
  return (
    <motion.div initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={SPRING}
      className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] whitespace-pre-line px-3.5 py-2.5 text-[15px] leading-snug shadow-sm ${mine
        ? 'rounded-2xl rounded-br-md bg-teal-700 text-white'
        : 'rounded-2xl rounded-bl-md bg-white text-slate-800 ring-1 ring-slate-100'}`}>
        {!mine && <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-teal-700"><Icon name="shield" className="h-3 w-3" />Qaqpan</div>}
        {rich(text)}
        {!mine && text.length === content.length && content.length > 40 && <div className="mt-2"><SpeakButton lang={lang} text={content} /></div>}
        {note && text.length === content.length && <div className="mt-1 text-[10px] text-slate-400">{note}</div>}
      </div>
    </motion.div>
  )
}

// models sometimes still use **bold**: render it instead of showing asterisks
function rich(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <b key={i}>{part.slice(2, -2)}</b> : <span key={i}>{part}</span>)
}
