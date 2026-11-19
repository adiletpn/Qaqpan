import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api, type Lang } from '../api'
import { tr } from '../i18n'
import { buzz, EASE, SPRING } from '../motion'
import { Header, Icon } from '../ui'

type Msg = { role: 'user' | 'assistant'; content: string; offline?: boolean }

const QUICK: Record<Lang, string[]> = {
  ru: ['Мне звонят из банка — это правда?', 'Продавец на OLX просит предоплату', 'Пришло SMS про ЭЦП со ссылкой', 'Меня обманули, что делать?'],
  kk: ['Маған банктен қоңырау шалып тұр — рас па?', 'OLX-та сатушы алдын ала төлем сұрайды', 'ЭЦҚ туралы сілтемесі бар SMS келді', 'Мені алдады, не істеймін?'],
}

export function AssistantScreen({ clientId, lang, onBack }: { clientId: string; lang: Lang; onBack: () => void }) {
  const L = (k: Parameters<typeof tr>[1]) => tr(lang, k)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [msgs, busy])

  const send = async (content: string) => {
    const q = content.trim()
    if (!q || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: q }]
    setMsgs(next); setText(''); setBusy(true)
    try {
      const r = await api.assistant(clientId, lang, next.map(({ role, content }) => ({ role, content })))
      buzz(15)
      setMsgs(m => [...m, { role: 'assistant', content: r.reply, offline: r.source === 'offline' }])
    } catch (e) {
      setMsgs(m => [...m, { role: 'assistant', content: e instanceof Error ? e.message : L('error'), offline: true }])
    } finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-full flex-col">
      <Header title={L('assistant')} onBack={onBack} />
      <div className="flex-1 space-y-2.5 px-4 pb-4">
        <Bubble role="assistant" content={L('assistant_hello')} />
        <AnimatePresence initial={false}>
          {msgs.length === 0 && (
            <motion.div key="quick" exit={{ opacity: 0, height: 0 }} className="flex flex-wrap gap-2 pt-1">
              {QUICK[lang].map((q, i) => (
                <motion.button key={q} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.06, ease: EASE }}
                  whileTap={{ scale: 0.96 }} onClick={() => send(q)}
                  className="rounded-full bg-white px-3 py-2 text-left text-[13px] font-medium text-teal-800 shadow-sm ring-1 ring-teal-100">
                  {q}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        {msgs.map((m, i) => <Bubble key={i} role={m.role} content={m.content} note={m.offline ? L('ai_offline') : undefined} />)}
        {busy && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex w-16 items-center justify-center gap-1 rounded-2xl rounded-bl-md bg-white px-3 py-3 shadow-sm ring-1 ring-slate-100">
            {[0, 1, 2].map(d => (
              <motion.span key={d} className="h-1.5 w-1.5 rounded-full bg-teal-600" animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.15 }} />
            ))}
          </motion.div>
        )}
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

function Bubble({ role, content, note }: { role: Msg['role']; content: string; note?: string }) {
  const mine = role === 'user'
  return (
    <motion.div initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={SPRING}
      className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] whitespace-pre-line px-3.5 py-2.5 text-[15px] leading-snug shadow-sm ${mine
        ? 'rounded-2xl rounded-br-md bg-teal-700 text-white'
        : 'rounded-2xl rounded-bl-md bg-white text-slate-800 ring-1 ring-slate-100'}`}>
        {!mine && <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-teal-700"><Icon name="shield" className="h-3 w-3" />Qaqpan</div>}
        {rich(content)}
        {note && <div className="mt-1 text-[10px] text-slate-400">{note}</div>}
      </div>
    </motion.div>
  )
}

// models sometimes still use **bold**: render it instead of showing asterisks
function rich(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <b key={i}>{part.slice(2, -2)}</b> : <span key={i}>{part}</span>)
}
