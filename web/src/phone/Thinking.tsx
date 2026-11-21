import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import type { Lang } from '../api'

// Gemini-style «thinking» indicator in Qaqpan colours: a breathing shield with a slowly turning glow and a
// shimmering status line that changes every 1.8 s. No bubble — light and native. Only transform/opacity
// animate (plus a small background-position shimmer), so it stays smooth on 120 Hz screens.
const STATUS: Record<Lang, string[]> = {
  ru: ['Анализирую ситуацию…', 'Проверяю признаки мошенничества…', 'Готовлю рекомендацию…'],
  kk: ['Жағдайды талдап жатырмын…', 'Алаяқтық белгілерін тексеріп жатырмын…', 'Ұсыныс дайындап жатырмын…'],
}

export function Thinking({ lang }: { lang: Lang }) {
  const [n, setN] = useState(0)
  useEffect(() => { const t = setInterval(() => setN(x => (x + 1) % STATUS[lang].length), 1800); return () => clearInterval(t) }, [lang])
  return (
    <div className="flex h-10 items-center gap-2.5 pl-1" role="status" aria-live="polite">
      <span className="qq-orb relative grid h-8 w-8 shrink-0 place-items-center">
        <span className="qq-glow absolute inset-0 rounded-full" />
        <svg className="qq-breathe relative h-[22px] w-[22px]" viewBox="0 0 24 24" aria-hidden>
          <defs>
            <linearGradient id="qq-shield" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#74C69D" /><stop offset="55%" stopColor="#40916C" /><stop offset="100%" stopColor="#2D6A4F" />
            </linearGradient>
          </defs>
          <path d="M12 2.5 4.5 5.4v5.9c0 4.6 3.1 8.6 7.5 10.2 4.4-1.6 7.5-5.6 7.5-10.2V5.4L12 2.5Z" fill="url(#qq-shield)" />
          <path d="m8.6 12.2 2.3 2.3 4.6-4.8" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="relative h-5 min-w-0 flex-1 overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span key={n} className="qq-shimmer absolute left-0 top-0 whitespace-nowrap text-[14px] font-medium"
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.28, ease: [0.32, 0.72, 0, 1] }}>
            {STATUS[lang][n]}
          </motion.span>
        </AnimatePresence>
      </span>
    </div>
  )
}
