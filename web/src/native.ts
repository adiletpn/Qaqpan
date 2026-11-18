import { useEffect } from 'react'
import { api } from './api'

// Bridge to the native wrapper (docs/ANDROID_WRAPPER.md). The wrapper injects
// window.QalqanNative.isOnCall() backed by AudioManager.getMode() / CXCallObserver.
// In a plain browser the bridge is absent and the call signal comes from the demo director.
declare global {
  interface Window { QalqanNative?: { isOnCall?: () => boolean } }
}

export const hasNativeBridge = () => typeof window !== 'undefined' && typeof window.QalqanNative?.isOnCall === 'function'

export function useNativeCallSignal(clientId: string) {
  useEffect(() => {
    if (!hasNativeBridge()) return
    let last: boolean | null = null
    const tick = () => {
      const now = Boolean(window.QalqanNative?.isOnCall?.())
      if (now !== last) { last = now; api.nativeCall(clientId, now).catch(() => { last = null }) }
    }
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [clientId])
}
