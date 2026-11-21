import type { Lang } from '../api'

// Read a text aloud. In the Android app the WebView has no speech synthesis, so the app exposes a native
// channel (window.QaqpanSpeak, flutter_tts); in a browser the built-in Web Speech voice is used.
declare global { interface Window { QaqpanSpeak?: { postMessage: (m: string) => void } } }

const LOCALE: Record<Lang, string> = { ru: 'ru-RU', kk: 'kk-KZ' }

export const canSpeak = () => typeof window !== 'undefined' && (!!window.QaqpanSpeak || 'speechSynthesis' in window)

export function speak(text: string, lang: Lang, onEnd?: () => void) {
  const clean = text.replace(/\*\*/g, '').replace(/\s+/g, ' ').trim()
  if (window.QaqpanSpeak) {
    window.QaqpanSpeak.postMessage(JSON.stringify({ text: clean, lang: LOCALE[lang] }))
    setTimeout(() => onEnd?.(), Math.min(30_000, 400 + clean.length * 70))  // the native side has no end callback here
    return
  }
  const synth = window.speechSynthesis
  synth.cancel()
  const u = new SpeechSynthesisUtterance(clean)
  const voices = synth.getVoices()
  // Kazakh voices are rare on devices: fall back to Russian, which reads Cyrillic closely enough
  u.voice = voices.find(v => v.lang.toLowerCase().startsWith(lang)) ?? voices.find(v => v.lang.toLowerCase().startsWith('ru')) ?? null
  u.lang = u.voice?.lang ?? LOCALE[lang]
  u.rate = 0.92  // a little slower: the main listeners are 50+
  u.onend = () => onEnd?.()
  u.onerror = () => onEnd?.()
  synth.speak(u)
}

export function stopSpeaking() {
  if (window.QaqpanSpeak) window.QaqpanSpeak.postMessage(JSON.stringify({ stop: true }))
  else if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}
