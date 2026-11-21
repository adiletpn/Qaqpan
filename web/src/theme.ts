import { useEffect, useState } from 'react'

// «В стиле BCC»: the phone UI in BCC's public brand palette (brand book: Gold, Green, Black, White).
// Not a copy of the BCC app: no logo files, and a visible «prototype» ribbon. Open any page with ?theme=bcc
// (or press T on /stage) — it is remembered on the device; ?theme=default switches back.
export type Theme = 'default' | 'bcc'
const STORAGE = 'qaqpan.theme'
const EVENT = 'qaqpan-theme'

function read(): Theme {
  try { return localStorage.getItem(STORAGE) === 'bcc' ? 'bcc' : 'default' } catch { return 'default' }
}

export function setTheme(t: Theme) {
  try { localStorage.setItem(STORAGE, t) } catch { /* storage may be unavailable */ }
  window.dispatchEvent(new Event(EVENT))
}

export function captureTheme() {
  const t = new URLSearchParams(window.location.search).get('theme')
  if (t === 'bcc' || t === 'default') setTheme(t)
}

export function useTheme(): Theme {
  const [theme, set] = useState<Theme>(read)
  useEffect(() => {
    const h = () => set(read())
    window.addEventListener(EVENT, h)
    window.addEventListener('storage', h)  // other tabs and the stage phones follow the switch
    return () => { window.removeEventListener(EVENT, h); window.removeEventListener('storage', h) }
  }, [])
  return theme
}
