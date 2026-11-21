import { useEffect, useState } from 'react'

// Reveals a finished answer progressively (typewriter), ~1.4 s at most however long the text is.
export function useTypewriter(text: string, enabled: boolean, onTick?: () => void) {
  const [shown, setShown] = useState(enabled ? 0 : text.length)
  useEffect(() => {
    if (!enabled) { setShown(text.length); return }
    let raf = 0
    const t0 = performance.now()
    const cps = Math.max(70, text.length / 1.4)
    const tick = () => {
      const k = Math.min(text.length, Math.round(((performance.now() - t0) / 1000) * cps))
      setShown(k)
      onTick?.()
      if (k < text.length) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [text, enabled, onTick])
  return text.slice(0, shown)
}
