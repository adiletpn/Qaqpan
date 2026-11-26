import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import type { Lang, Reason } from '../api'
import { EASE } from '../motion'

// «Дәлел» — the evidence view: the message itself, with every suspicious place marked like a highlighter and
// numbered; each number has its explanation below. Tap a mark to light up its reason and the other way round.
type Seg = { text: string; n: number | null; first: boolean }

function segments(text: string, numbered: { n: number; spans: [number, number][] }[]): Seg[] {
  const owner: (number | null)[] = Array(text.length).fill(null)
  for (const { n, spans } of numbered) {
    for (const [a, b] of spans) for (let k = Math.max(0, a); k < Math.min(text.length, b); k++) owner[k] ??= n
  }
  const out: Seg[] = []
  const seen = new Set<number>()
  for (let k = 0; k < text.length; k++) {
    const n = owner[k]
    const last = out[out.length - 1]
    if (last && last.n === n) last.text += text[k]
    else { out.push({ text: text[k], n, first: n != null && !seen.has(n) }); if (n != null) seen.add(n) }
  }
  return out
}

export function Evidence({ text, reasons, lang }: { text: string; reasons: Reason[]; lang: Lang }) {
  const [active, setActive] = useState<number | null>(null)
  const { numbered, rest, segs } = useMemo(() => {
    // numbers follow the reading order of the message, not the order of the reasons
    const marked = reasons.filter(r => r.spans?.length).sort((x, y) => Math.min(...x.spans!.map(s => s[0])) - Math.min(...y.spans!.map(s => s[0])))
    const numbered = marked.map((r, k) => ({ ...r, n: k + 1, spans: r.spans! }))
    const rest = reasons.filter(r => !r.spans?.length)
    return { numbered, rest, segs: segments(text, numbered) }
  }, [text, reasons])
  const toggle = (n: number) => setActive(a => (a === n ? null : n))

  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1.5 text-[11px] font-semibold text-slate-400">{lang === 'kk' ? 'Алдау қай жерде' : 'Где подвох'}</div>
        <div className="max-h-48 overflow-y-auto rounded-2xl bg-slate-50 p-3 text-[14px] leading-[1.75] text-slate-700 ring-1 ring-slate-100">
          {segs.map((s, k) => s.n == null ? <span key={k}>{s.text}</span> : (
            <mark key={k} onClick={() => toggle(s.n!)} style={{ animationDelay: `${0.25 + (s.n - 1) * 0.22}s` }}
              className={`qq-mark cursor-pointer rounded-[4px] px-[1px] text-slate-900 transition-shadow ${active === s.n ? 'qq-mark-on' : ''}`}>
              {s.text}
              {s.first && <sup className="ml-0.5 inline-grid h-[15px] min-w-[15px] place-items-center rounded-full bg-amber-500 px-1 align-[2px] text-[10px] font-semibold leading-none text-white">{s.n}</sup>}
            </mark>
          ))}
        </div>
      </div>
      <ul className="space-y-1.5 text-sm">
        {numbered.map((r, i) => (
          <motion.li key={r.n} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.08, duration: 0.3, ease: EASE }}
            onClick={() => toggle(r.n)}
            className={`flex cursor-pointer gap-2 rounded-xl px-2 py-1.5 transition-colors duration-200 ${active === r.n ? 'bg-amber-50 ring-1 ring-amber-200' : ''}`}>
            <span className="mt-[1px] grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full bg-amber-500 text-[11px] font-semibold text-white">{r.n}</span>
            <span>{r.text}</span>
          </motion.li>
        ))}
        {rest.map((r, i) => (
          <motion.li key={`r${i}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + (numbered.length + i) * 0.08, duration: 0.3, ease: EASE }}
            className="flex gap-2 px-2"><span className="w-[18px] shrink-0 text-center text-slate-400">•</span>{r.text}</motion.li>
        ))}
      </ul>
    </div>
  )
}
