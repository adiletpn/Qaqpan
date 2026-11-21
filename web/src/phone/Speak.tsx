import { useEffect, useState } from 'react'
import type { Lang } from '../api'
import { Icon } from '../ui'
import { canSpeak, speak, stopSpeaking } from './speech'

// «Озвучить»: one tap reads the verdict or the advice aloud — for clients 50+ without their glasses.
export function SpeakButton({ text, lang, tone = 'light' }: { text: string; lang: Lang; tone?: 'light' | 'dark' }) {
  const [on, setOn] = useState(false)
  useEffect(() => () => { if (on) stopSpeaking() }, [on])
  if (!canSpeak() || !text) return null
  const toggle = () => {
    if (on) { stopSpeaking(); setOn(false); return }
    setOn(true)
    speak(text, lang, () => setOn(false))
  }
  const label = on ? (lang === 'kk' ? 'Тоқтату' : 'Стоп') : (lang === 'kk' ? 'Дауыстап оқу' : 'Озвучить')
  return (
    <button onClick={toggle} aria-label={label}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition active:scale-95 ${tone === 'dark'
        ? 'bg-white/20 text-white' : on ? 'bg-teal-700 text-white' : 'bg-teal-50 text-teal-800 ring-1 ring-teal-100'}`}>
      <Icon name={on ? 'stop' : 'speaker'} className="h-3.5 w-3.5" />{label}
    </button>
  )
}
