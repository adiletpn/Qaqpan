import { useEffect, useState } from 'react'
import { api } from './api'

// The Qaqpan bot in Telegram: «become the son» — scan, and the mother's push arrives in your real Telegram
// with «Отклонить / Разрешить». Hidden when the server has no bot token.
let cached: string | null | undefined
export function useBot(): string | null {
  const [u, setU] = useState<string | null>(cached ?? null)
  useEffect(() => {
    if (cached !== undefined) return
    api.health().then(h => { cached = h.telegram?.username ?? null; setU(cached) }).catch(() => { cached = null })
  }, [])
  return u
}

export const guardianLink = (bot: string, sandbox: string | null) => `https://t.me/${bot}?start=g_${sandbox ?? 'stage'}`

export function useQr(url: string | null, size = 220) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!url) return
    // the QR library is loaded only when a QR is actually shown
    import('qrcode').then(m => m.default.toDataURL(url, { width: size, margin: 1, color: { dark: '#0f172a', light: '#ffffff' } })).then(setSrc).catch(() => setSrc(null))
  }, [url, size])
  return src
}

