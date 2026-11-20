import { useEffect } from 'react'
import { api } from './api'

// Bridge to the native app (Flutter Android app in /mobile, or the wrapper in docs/ANDROID_WRAPPER.md).
// Two ways the native side can expose the call state — both read only the FACT of a call:
//   1. window.QaqpanNative.isOnCall()  — a synchronous JS interface (WebView addJavascriptInterface)
//   2. window.__qaqpanOnCall = true|false — a flag the app pushes every second (Flutter WebView)
// In a plain browser neither exists and the call signal comes from the demo director.
declare global {
  interface Window {
    QaqpanNative?: { isOnCall?: () => boolean }
    __qaqpanOnCall?: boolean
  }
}

function readNativeCall(): boolean | null {
  if (typeof window === 'undefined') return null
  if (typeof window.QaqpanNative?.isOnCall === 'function') return Boolean(window.QaqpanNative.isOnCall())
  if (typeof window.__qaqpanOnCall === 'boolean') return window.__qaqpanOnCall
  return null
}

export const hasNativeBridge = () => readNativeCall() !== null

export function useNativeCallSignal(clientId: string) {
  useEffect(() => {
    let last: boolean | null = null
    // the bridge may appear after the page has loaded, so keep checking instead of deciding once
    const tick = () => {
      const now = readNativeCall()
      if (now === null || now === last) return
      last = now
      api.nativeCall(clientId, now).catch(() => { last = null })
    }
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [clientId])
}
